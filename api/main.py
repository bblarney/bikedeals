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
from sqlalchemy import distinct, func, literal, select, text, union_all, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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

_SORT_COLUMNS = {
    "discount_desc": Bike.discount_percentage.desc(),
    "price_asc": Bike.price_sale.asc(),
    "price_desc": Bike.price_sale.desc(),
    "clicks_desc": Bike.click_count.desc(),
}

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

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()

    order_col = _SORT_COLUMNS.get(sort, Bike.discount_percentage.desc())
    rows = await db.execute(base.order_by(order_col).limit(limit).offset(offset))
    bikes = rows.scalars().all()

    results = []
    for bike_obj in bikes:
        br = BikeResponse.model_validate(bike_obj)
        br.sku = bike_obj.sku
        br.sku_vendor_count = (
            product_vendor_counts.get(bike_obj.product_key, 0) if bike_obj.product_key else 0
        )
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

    def facet_select(name: str, col, ignored: str, *extra_where):
        """One facet's options, labelled so several can share a round trip."""
        base = (
            select(literal(name).label("facet"), col.label("value"))
            .distinct()
            .where(Bike.in_stock == True, *extra_where)  # noqa: E712
        )
        overrides = f.copy()
        overrides[ignored] = [] if isinstance(f[ignored], list) else (0 if ignored == "min_discount" else None)
        # Range filters don't narrow discrete facet options — an out-of-range
        # price shouldn't wipe out the category/brand/size lists.
        overrides["min_price"] = None
        overrides["max_price"] = None
        overrides["min_discount"] = 0
        return _apply_filters(base, **overrides)

    # The seven facets go to the database as ONE statement.
    #
    # They used to be seven separate awaits, and a note here explained that
    # asyncio.gather could not parallelise them because an async session
    # serializes within its connection. That framing had the wrong target:
    # against a remote Postgres the cost is not scan time, it is eleven
    # sequential round trips. In production this endpoint took ~0.8s while
    # /bikes — which does real work over the same table — took ~0.28s.
    #
    # UNION ALL removes the round trips instead of trying to overlap them, and
    # needs no extra connections from the pool. Each branch still filters
    # independently, so the facet-excludes-itself rule is unchanged; the label
    # column is what lets one result set be split back apart.
    in_stock_clause = Bike.in_stock == True  # noqa: E712
    facets_stmt = union_all(
        facet_select("categories", Bike.category, "category"),
        facet_select("cities", Bike.city, "city", Bike.city.isnot(None)),
        facet_select("sizes", Bike.frame_size, "size"),
        facet_select("vendors", Bike.vendor_name, "vendor"),
        facet_select("brands", Bike.brand, "brand"),
        facet_select("frame_materials", Bike.frame_material, "frame_material",
                     Bike.frame_material.isnot(None)),
        facet_select("drivetrain_groupsets", Bike.drivetrain_groupset, "drivetrain_groupset",
                     Bike.drivetrain_groupset.isnot(None)),
    )
    facet_rows = await db.execute(facets_stmt)
    facets: dict[str, list[str]] = {
        "categories": [], "cities": [], "sizes": [], "vendors": [],
        "brands": [], "frame_materials": [], "drivetrain_groupsets": [],
    }
    for name, value in facet_rows.all():
        facets[name].append(value)
    # Sorted here rather than with a per-branch ORDER BY, which UNION ALL would
    # not preserve anyway. These are a few hundred strings.
    for values in facets.values():
        values.sort()

    # Discount range and the total share a WHERE clause, so they share a query.
    totals_r = await db.execute(
        select(
            func.min(Bike.discount_percentage),
            func.max(Bike.discount_percentage),
            func.count(),
        ).where(in_stock_clause)
    )
    # Price range is separate because it alone applies the active non-price
    # filters — the number drives the price slider's bounds.
    price_r = await db.execute(
        _apply_filters(
            select(func.min(Bike.price_sale), func.max(Bike.price_sale)).where(in_stock_clause),
            **{**f, "min_price": None, "max_price": None},
        )
    )
    last_scraped_r = await db.execute(
        select(func.max(ScrapeLog.run_at)).where(ScrapeLog.status == "ok")
    )
    discount_min, discount_max, total_bikes = totals_r.one()
    price_row = price_r.one()

    response.headers["Cache-Control"] = CACHE_FILTERS

    return FiltersResponse(
        categories=facets["categories"],
        cities=facets["cities"],
        sizes=facets["sizes"],
        vendors=facets["vendors"],
        brands=facets["brands"],
        frame_materials=facets["frame_materials"],
        drivetrain_groupsets=facets["drivetrain_groupsets"],
        discount_range={"min": discount_min or 0, "max": discount_max or 0},
        price_range={"min": float(price_row[0] or 0), "max": float(price_row[1] or 0)},
        total_bikes=total_bikes,
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

    new_today_r        = await db.execute(select(func.count()).where(in_stock, Bike.scraped_at >= cutoff))
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
    rows = await db.execute(
        select(Bike.id, Bike.last_seen_at)
        .where(Bike.in_stock == True)  # noqa: E712
        .order_by(Bike.last_seen_at.desc())
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
