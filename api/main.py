import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import distinct, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.db import get_db, get_engine
from api.models import Base, Bike, PriceEvent, ScrapeLog, Subscriber
from api.schemas import (
    BikeDetailResponse,
    BikeResponse,
    FiltersResponse,
    MessageResponse,
    OfferResponse,
    PaginatedBikes,
    PricePoint,
    StatsResponse,
    SubscribeRequest,
    UnsubscribeRequest,
    VariantResponse,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)
logger = logging.getLogger("bikegrid.api")

_AFFILIATE_URLS: dict[str, str] = {
    k: v
    for k, v in {
        "Bikes Online": os.getenv("IMPACT_BIKESONLINE_URL", ""),
    }.items()
    if v
}


def _apply_affiliate_url(vendor_name: str, product_url: str) -> str:
    base = _AFFILIATE_URLS.get(vendor_name)
    if base:
        return f"{base}?u={quote(product_url, safe='')}"
    return product_url


# A competing offer is a *vendor*, not a storefront.
#
# This used to key on (vendor_name, city), which is the right identity for "where
# can I collect this" but the wrong one for "who else sells it". Chains list one
# national catalogue at one price across every city, so counting storefronts
# inflated the badge badly: SKU MEKI2192036 claimed 21 shops when it is 4
# vendors — 99 Bikes and Bicycle Centre Australia each counted once per city.
# Against the live feed that padding touched 8,097 listings (21% of the feed).
#
# Cities are not lost: an offer carries location_count and the city of its
# cheapest listing, so the UI can still say "also at 7 other 99 Bikes stores".
def _vendor_key():
    return Bike.vendor_name


# A chain's storefronts are one listing, not N.
#
# A vendor with a `cities:` list in its YAML gets one row per city, because
# bikes.id hashes the city in (scrapers.models.make_bike_id). For a chain that
# publishes one national catalogue at one price, those rows are the *same
# listing* seen from N shopfronts, and the feed showed every one of them:
# 99 Bikes was 8,616 of 38,724 in-stock rows (~1,077 products x 8 cities),
# Bicycle Centre 5,643 (~513 x 11), Bikes Online 2,875 (575 x 5). Three chains
# alone were 44% of the catalogue, and the duplicates sat next to each other in
# the grid because they sort identically.
#
# The detail endpoint already resolved the same problem for cross-shop offers
# ("a competing offer is a vendor, not a storefront", see _vendor_key). This is
# that rule applied to the feed itself: collapse to one row and carry a
# location_count so the UI can still say "at 8 stores".
#
# Grouping on product_url rather than sku is deliberate — 13% of listings have
# no SKU, and the URL is what actually distinguishes two products at one vendor.
# frame_size stays in the key so a chain's S/M/L remain separate listings.
_STOREFRONT_GROUP = (Bike.vendor_name, Bike.product_url, Bike.frame_size)

# Which storefront represents the group. Cheapest first (chains price nationally,
# but if one city undercuts, that is the honest row to show), then city, then id
# as a deterministic tiebreak so the choice is stable across requests and
# backends. The sitemap MUST order identically or it advertises a different URL
# than the feed links to.
_STOREFRONT_PICK = (Bike.price_sale.asc(), Bike.city.asc(), Bike.id.asc())


def _storefront_rank():
    return func.row_number().over(
        partition_by=_STOREFRONT_GROUP, order_by=_STOREFRONT_PICK
    ).label("storefront_rank")


def _storefront_count():
    return func.count().over(partition_by=_STOREFRONT_GROUP).label("location_count")


def _collapse_storefronts(query):
    """One row per (vendor, product, size), with a location_count.

    Window functions run after WHERE, so any filter — notably ?city= — narrows
    the rows *before* the collapse. Filtering to one city therefore leaves each
    chain listing with location_count 1, which is correct: in that city it is
    one shop.
    """
    ranked = query.add_columns(_storefront_rank(), _storefront_count()).subquery()
    return aliased(Bike, ranked), ranked


def _distinct_listing_count(*where_clauses):
    """COUNT of listings after chain collapse, for the trust-facing totals.

    GROUP BY rather than COUNT(DISTINCT a, b, c): the multi-column form is
    Postgres-only and the test suite runs on SQLite.
    """
    grouped = (
        select(Bike.vendor_name, Bike.product_url, Bike.frame_size)
        .where(*where_clauses)
        .group_by(Bike.vendor_name, Bike.product_url, Bike.frame_size)
        .subquery()
    )
    return select(func.count()).select_from(grouped)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all is a zero-setup dev convenience only. On Postgres (prod) Alembic
    # owns the schema (`alembic upgrade head`); calling create_all there silently
    # creates new *tables* outside Alembic's tracking, so the next migration that
    # tries to create the same table fails with DuplicateTableError. Restrict it
    # to SQLite — mirrors scrapers/run.py. See migrations/.
    engine = get_engine()
    if engine.url.get_backend_name() == "sqlite":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="BikeGrid API", version="1.0", lifespan=lifespan)

_default_origins = "https://bikegrid.com.au,https://www.bikegrid.com.au"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()]

# Public site origin (the frontend), used to build absolute sitemap URLs.
SITE_URL = os.getenv("SITE_URL", "https://bikegrid.com.au").rstrip("/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept", "Origin"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # Log the full traceback server-side, but never leak it to the client.
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred."}},
    )

# (attribute, descending?) rather than a bound Bike column, because the feed
# orders the *collapsed* subquery alias, not the base table.
_SORT_COLUMNS = {
    "discount_desc": ("discount_percentage", True),
    "price_asc": ("price_sale", False),
    "price_desc": ("price_sale", True),
    "clicks_desc": ("click_count", True),
}


def _order_by(entity, sort: str):
    """Sort expression plus a deterministic tiebreak.

    Every sort key has enormous ties — half the feed sits at 0% discount — and
    without a unique tiebreak the DB is free to return them in a different order
    per query. That silently drops and repeats rows across LIMIT/OFFSET pages.
    """
    name, descending = _SORT_COLUMNS.get(sort, _SORT_COLUMNS["discount_desc"])
    col = getattr(entity, name)
    return [col.desc() if descending else col.asc(), entity.id.asc()]

CACHE_BIKES = "max-age=300"   # 5 min — bikes update after each scrape run
CACHE_FILTERS = "max-age=60"  # 1 min — filters change when vendors are added
CACHE_STATS = "max-age=300"   # 5 min — stats change only after a scrape run

_ADDED_SINCE_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def _added_since_cutoff(added_since: str) -> datetime:
    # Quantize "now" to the start of the current hour so identical requests
    # within the hour share a cache key and a DB query plan.
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return now - timedelta(days=_ADDED_SINCE_DAYS[added_since])


def _apply_filters(
    query,
    *,
    city: list[str],
    category: list[str],
    size: list[str],
    vendor: list[str],
    brand: list[str],
    frame_material: list[str],
    drivetrain_groupset: list[str],
    min_discount: int,
    q: str | None,
    added_since: str | None,
    min_price: float | None = None,
    max_price: float | None = None,
    sku: str | None = None,
    product_key: str | None = None,
):
    if city:
        query = query.where(func.lower(Bike.city).in_([c.lower() for c in city]))
    if category:
        query = query.where(Bike.category.in_(category))
    if size:
        query = query.where(Bike.frame_size.in_(size))
    if vendor:
        query = query.where(Bike.vendor_name.in_(vendor))
    if brand:
        query = query.where(Bike.brand.in_(brand))
    if frame_material:
        query = query.where(Bike.frame_material.in_(frame_material))
    if drivetrain_groupset:
        query = query.where(Bike.drivetrain_groupset.in_(drivetrain_groupset))
    if min_discount > 0:
        query = query.where(Bike.discount_percentage >= min_discount)
    if min_price is not None:
        query = query.where(Bike.price_sale >= min_price)
    if max_price is not None:
        query = query.where(Bike.price_sale <= max_price)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            func.lower(Bike.brand).like(pattern)
            | func.lower(Bike.model_name).like(pattern)
        )
    if added_since:
        query = query.where(Bike.scraped_at >= _added_since_cutoff(added_since))
    # Prefer product_key: `sku` alone collides across brands (see
    # scrapers.models.make_product_key), so "show me every shop selling this"
    # returned unrelated bikes. `sku` is kept for back-compat with any saved or
    # shared links.
    if product_key:
        query = query.where(Bike.product_key == product_key)
    elif sku:
        query = query.where(Bike.sku == sku)
    return query


@app.get("/api/v1/health")
async def health(response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.warning("Health check failed: database unreachable", exc_info=True)
        response.status_code = 503
        return {"status": "degraded", "database": "unreachable"}
    return {"status": "ok", "database": "connected"}


@app.get("/api/v1/bikes", response_model=PaginatedBikes)
@limiter.limit("120/minute")
async def get_bikes(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    category: list[str] = Query(default=[]),
    city: list[str] = Query(default=[]),
    size: list[str] = Query(default=[]),
    vendor: list[str] = Query(default=[]),
    brand: list[str] = Query(default=[]),
    frame_material: list[str] = Query(default=[]),
    drivetrain_groupset: list[str] = Query(default=[]),
    min_discount: int = Query(default=0, ge=0, le=100),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    in_stock: bool = True,
    q: str | None = Query(default=None, max_length=100),
    sort: str = Query(default="discount_desc", pattern="^(discount_desc|price_asc|price_desc|clicks_desc)$"),
    added_since: str | None = Query(default=None, pattern="^(day|week|month|year)$"),
    sku: str | None = None,
    product_key: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    # Single GROUP BY: count distinct vendors per product.
    vendor_key = _vendor_key()
    product_counts_q = (
        select(Bike.product_key, func.count(distinct(vendor_key)).label("cnt"))
        .where(Bike.product_key.isnot(None), Bike.in_stock == True)  # noqa: E712
        .group_by(Bike.product_key)
        .having(func.count(distinct(vendor_key)) >= 2)
    )
    product_counts_r = await db.execute(product_counts_q)
    product_vendor_counts: dict[str, int] = {
        row.product_key: row.cnt for row in product_counts_r.all()
    }

    base = select(Bike)
    base = _apply_filters(
        base,
        city=city, category=category, size=size, vendor=vendor, brand=brand,
        frame_material=frame_material, drivetrain_groupset=drivetrain_groupset,
        min_discount=min_discount, min_price=min_price, max_price=max_price,
        q=q, added_since=added_since, sku=sku, product_key=product_key,
    )
    if in_stock:
        base = base.where(Bike.in_stock == True)  # noqa: E712

    # One row per chain listing rather than one per storefront.
    listing, ranked = _collapse_storefronts(base)
    collapsed = (
        select(listing, ranked.c.location_count)
        .where(ranked.c.storefront_rank == 1)
    )

    count_result = await db.execute(select(func.count()).select_from(collapsed.subquery()))
    total = count_result.scalar_one()

    rows = await db.execute(
        collapsed.order_by(*_order_by(listing, sort)).limit(limit).offset(offset)
    )

    results = []
    for bike_obj, location_count in rows.all():
        br = BikeResponse.model_validate(bike_obj)
        br.sku = bike_obj.sku
        br.sku_vendor_count = (
            product_vendor_counts.get(bike_obj.product_key, 0) if bike_obj.product_key else 0
        )
        br.location_count = location_count
        br.product_url = _apply_affiliate_url(bike_obj.vendor_name, br.product_url)
        results.append(br)

    response.headers["Cache-Control"] = CACHE_BIKES
    return PaginatedBikes(total=total, limit=limit, offset=offset, results=results)


@app.get("/api/v1/bikes/{bike_id}", response_model=BikeDetailResponse)
@limiter.limit("120/minute")
async def get_bike(
    request: Request,
    response: Response,
    bike_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    primary = await db.get(Bike, bike_id)
    if primary is None:
        raise HTTPException(status_code=404, detail="Bike not found")

    # Cross-shop offers: every in-stock listing of the same product, collapsed to
    # the cheapest listing per vendor. Keyed on product_key, not sku — see
    # _vendor_key and scrapers.models.make_product_key for why matching on the
    # raw SKU merged unrelated bikes. No product_key → the bike stands alone.
    if primary.product_key:
        rows = await db.execute(
            select(Bike)
            .where(Bike.product_key == primary.product_key, Bike.in_stock == True)  # noqa: E712
            .order_by(Bike.price_sale.asc())
        )
        candidates = rows.scalars().all()
    else:
        candidates = [primary] if primary.in_stock else []

    # Rows arrive price-ascending, so the first row seen per vendor is its
    # cheapest; the rest of that vendor's storefronts only bump location_count.
    cheapest_per_vendor: dict[str, Bike] = {}
    locations: dict[str, set[str]] = {}
    for b in candidates:
        cheapest_per_vendor.setdefault(b.vendor_name, b)
        if b.city:
            locations.setdefault(b.vendor_name, set()).add(b.city)

    offers = [
        OfferResponse(
            bike_id=b.id,
            vendor_name=b.vendor_name,
            city=b.city,
            frame_size=b.frame_size,
            price_original=b.price_original,
            price_sale=b.price_sale,
            discount_percentage=b.discount_percentage,
            in_stock=b.in_stock,
            product_url=_apply_affiliate_url(b.vendor_name, b.product_url),
            last_seen_at=b.last_seen_at,
            location_count=len(locations.get(b.vendor_name, ())) or 1,
        )
        for b in sorted(cheapest_per_vendor.values(), key=lambda x: x.price_sale)
    ]

    # Other frame sizes of the same model, cheapest listing per size.
    var_rows = await db.execute(
        select(Bike)
        .where(
            Bike.brand == primary.brand,
            Bike.model_name == primary.model_name,
            Bike.in_stock == True,  # noqa: E712
        )
        .order_by(Bike.price_sale.asc())
    )
    cheapest_per_size: dict[str, Bike] = {}
    for b in var_rows.scalars().all():
        if b.frame_size not in cheapest_per_size:
            cheapest_per_size[b.frame_size] = b
    variants = [
        VariantResponse(
            bike_id=b.id,
            frame_size=b.frame_size,
            price_sale=b.price_sale,
            in_stock=b.in_stock,
        )
        for b in sorted(cheapest_per_size.values(), key=lambda x: x.frame_size or "")
    ]

    detail = BikeDetailResponse.model_validate(primary)
    detail.sku = primary.sku
    detail.product_url = _apply_affiliate_url(primary.vendor_name, primary.product_url)
    detail.offers = offers
    detail.shop_count = len(offers)
    detail.lowest_price = offers[0].price_sale if offers else primary.price_sale
    detail.sku_vendor_count = len(offers) if len(offers) >= 2 else 0
    detail.variants = variants

    response.headers["Cache-Control"] = CACHE_BIKES
    return detail


@app.get("/api/v1/bikes/{bike_id}/price-history", response_model=list[PricePoint])
@limiter.limit("120/minute")
async def get_price_history(
    request: Request,
    response: Response,
    bike_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # 404 on an unknown bike so the chart can distinguish "no such deal" from
    # "deal with no recorded changes yet" (mirrors get_bike).
    if await db.get(Bike, bike_id) is None:
        raise HTTPException(status_code=404, detail="Bike not found")

    rows = await db.execute(
        select(PriceEvent)
        .where(PriceEvent.bike_id == bike_id)
        .order_by(PriceEvent.observed_at.asc())
    )
    response.headers["Cache-Control"] = CACHE_BIKES
    return list(rows.scalars().all())


@app.post("/api/v1/bikes/{bike_id}/click", status_code=204)
@limiter.limit("30/minute")
async def record_click(
    request: Request,
    bike_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        update(Bike)
        .where(Bike.id == bike_id)
        .values(click_count=Bike.click_count + 1)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Bike not found")
    await db.commit()


@app.get("/api/v1/meta/filters", response_model=FiltersResponse)
@limiter.limit("120/minute")
async def get_filters(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    category: list[str] = Query(default=[]),
    city: list[str] = Query(default=[]),
    size: list[str] = Query(default=[]),
    vendor: list[str] = Query(default=[]),
    brand: list[str] = Query(default=[]),
    frame_material: list[str] = Query(default=[]),
    drivetrain_groupset: list[str] = Query(default=[]),
    min_discount: int = Query(default=0, ge=0, le=100),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    q: str | None = Query(default=None, max_length=100),
    added_since: str | None = Query(default=None, pattern="^(day|week|month|year)$"),
):
    # Faceted filters: each facet's options are computed with all *other* active
    # filters applied (the facet excludes itself). That keeps each list relevant
    # without trapping the user in a single-option facet.
    f = dict(
        city=city, category=category, size=size, vendor=vendor, brand=brand,
        frame_material=frame_material, drivetrain_groupset=drivetrain_groupset,
        min_discount=min_discount, min_price=min_price, max_price=max_price,
        q=q, added_since=added_since,
    )

    def facet_query(col, ignored: str):
        base = select(col).distinct().where(Bike.in_stock == True).order_by(col)  # noqa: E712
        overrides = f.copy()
        overrides[ignored] = [] if isinstance(f[ignored], list) else (0 if ignored == "min_discount" else None)
        # Range filters don't narrow discrete facet options — an out-of-range
        # price shouldn't wipe out the category/brand/size lists.
        overrides["min_price"] = None
        overrides["max_price"] = None
        overrides["min_discount"] = 0
        return _apply_filters(base, **overrides)

    # NOTE: SQLAlchemy's async session serializes within a single connection,
    # so asyncio.gather here would raise InvalidRequestError. Real concurrency
    # needs separate sessions from the pool; that's a larger refactor.
    in_stock_clause = Bike.in_stock == True  # noqa: E712
    categories_r    = await db.execute(facet_query(Bike.category,    "category"))
    cities_r        = await db.execute(facet_query(Bike.city,        "city").where(Bike.city.isnot(None)))
    sizes_r         = await db.execute(facet_query(Bike.frame_size,  "size"))
    vendors_r       = await db.execute(facet_query(Bike.vendor_name, "vendor"))
    brands_r        = await db.execute(facet_query(Bike.brand,       "brand"))
    materials_r     = await db.execute(
        facet_query(Bike.frame_material, "frame_material").where(Bike.frame_material.isnot(None))
    )
    groupsets_r     = await db.execute(
        facet_query(Bike.drivetrain_groupset, "drivetrain_groupset").where(Bike.drivetrain_groupset.isnot(None))
    )
    discount_r      = await db.execute(select(func.min(Bike.discount_percentage), func.max(Bike.discount_percentage)).where(in_stock_clause))
    # Price range computed with all non-price filters applied
    price_base = _apply_filters(
        select(func.min(Bike.price_sale), func.max(Bike.price_sale)).where(in_stock_clause),
        **{**f, "min_price": None, "max_price": None},
    )
    price_r         = await db.execute(price_base)
    # Chain-collapsed, so the header's "N bikes" matches what the feed returns.
    total_r         = await db.execute(_distinct_listing_count(in_stock_clause))
    last_scraped_r  = await db.execute(select(func.max(ScrapeLog.run_at)).where(ScrapeLog.status == "ok"))
    discount_row = discount_r.one()
    price_row = price_r.one()

    response.headers["Cache-Control"] = CACHE_FILTERS

    return FiltersResponse(
        categories=[r[0] for r in categories_r.all()],
        cities=[r[0] for r in cities_r.all()],
        sizes=[r[0] for r in sizes_r.all()],
        vendors=[r[0] for r in vendors_r.all()],
        brands=[r[0] for r in brands_r.all()],
        frame_materials=[r[0] for r in materials_r.all()],
        drivetrain_groupsets=[r[0] for r in groupsets_r.all()],
        discount_range={"min": discount_row[0] or 0, "max": discount_row[1] or 0},
        price_range={"min": float(price_row[0] or 0), "max": float(price_row[1] or 0)},
        total_bikes=total_r.scalar_one(),
        last_scraped_at=last_scraped_r.scalar_one(),
    )


@app.post("/api/v1/subscribe", status_code=201, response_model=MessageResponse)
@limiter.limit("5/minute")
async def subscribe(
    request: Request,
    body: SubscribeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    subscriber = Subscriber(
        email=body.email,
        token=secrets.token_urlsafe(32),
        subscribed_at=datetime.now(timezone.utc),
    )
    db.add(subscriber)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Already subscribed")
    return MessageResponse(message="Subscribed")


# POST (not GET) so that email-client / CDN link prefetching cannot trigger an
# accidental unsubscribe, and so the token is not captured in proxy access logs.
@app.post("/api/v1/unsubscribe", status_code=200, response_model=MessageResponse)
@limiter.limit("10/minute")
async def unsubscribe(
    request: Request,
    body: UnsubscribeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Subscriber).where(Subscriber.token == body.token))
    subscriber = result.scalar_one_or_none()
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Token not found")
    await db.delete(subscriber)
    await db.commit()
    return MessageResponse(message="Unsubscribed")


@app.get("/api/v1/meta/stats", response_model=StatsResponse)
@limiter.limit("120/minute")
async def get_stats(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    in_stock = Bike.in_stock == True  # noqa: E712
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    new_today_r        = await db.execute(_distinct_listing_count(in_stock, Bike.scraped_at >= cutoff))
    shops_r            = await db.execute(select(func.count(Bike.vendor_name.distinct())).where(in_stock))
    biggest_discount_r = await db.execute(select(func.max(Bike.discount_percentage)).where(in_stock))
    avg_discount_r     = await db.execute(
        select(func.round(func.avg(Bike.discount_percentage))).where(in_stock, Bike.discount_percentage > 0)
    )

    response.headers["Cache-Control"] = CACHE_STATS
    return StatsResponse(
        new_today=new_today_r.scalar_one() or 0,
        shops_tracked=shops_r.scalar_one() or 0,
        biggest_discount=biggest_discount_r.scalar_one() or 0,
        avg_discount=int(avg_discount_r.scalar_one() or 0),
    )


@app.get("/sitemap.xml")
@limiter.limit("30/minute")
async def sitemap(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # One <url> per in-stock bike detail page so Google can discover them, plus
    # the core landing pages. Without this the detail pages never get crawled.
    #
    # Chain storefronts are collapsed with the same rule (and the same pick
    # order) the feed uses, so we advertise exactly the URL the feed links to.
    # Previously this listed all 38,725 rows — ~44% of them near-identical pages
    # for one chain product in 8-11 cities, which is duplicate content pointed
    # at Google on purpose, on a domain that also has a finite crawl budget.
    ranked = (
        select(Bike.id, Bike.last_seen_at, _storefront_rank())
        .where(Bike.in_stock == True)  # noqa: E712
        .subquery()
    )
    rows = await db.execute(
        select(ranked.c.id, ranked.c.last_seen_at)
        .where(ranked.c.storefront_rank == 1)
        .order_by(ranked.c.last_seen_at.desc())
    )

    def url_entry(loc: str, lastmod: datetime | None = None) -> str:
        parts = [f"<loc>{xml_escape(loc)}</loc>"]
        if lastmod is not None:
            parts.append(f"<lastmod>{lastmod.date().isoformat()}</lastmod>")
        return f"<url>{''.join(parts)}</url>"

    entries = [url_entry(f"{SITE_URL}/")]
    entries.extend(
        url_entry(f"{SITE_URL}/bikes/{bike_id}", last_seen_at)
        for bike_id, last_seen_at in rows.all()
    )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{''.join(entries)}"
        "</urlset>"
    )
    return Response(
        content=body,
        media_type="application/xml",
        headers={"Cache-Control": "max-age=3600"},
    )
