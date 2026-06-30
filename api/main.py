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


# A shop is a (vendor_name, city) pair: vendor_name alone is not unique because
# chain stores (e.g. Giant) share a name across cities. Used for both the
# per-SKU shop count and the cross-shop offers list.
def _shop_key():
    return Bike.vendor_name + "|||" + func.coalesce(Bike.city, "")


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
    if sku:
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
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    # Single GROUP BY: count distinct (vendor_name, city) pairs per SKU.
    shop_key = _shop_key()
    sku_counts_q = (
        select(Bike.sku, func.count(distinct(shop_key)).label("cnt"))
        .where(Bike.sku.isnot(None), Bike.sku != "", Bike.in_stock == True)  # noqa: E712
        .group_by(Bike.sku)
        .having(func.count(distinct(shop_key)) >= 2)
    )
    sku_counts_r = await db.execute(sku_counts_q)
    sku_vendor_counts: dict[str, int] = {row.sku: row.cnt for row in sku_counts_r.all()}

    base = select(Bike)
    base = _apply_filters(
        base,
        city=city, category=category, size=size, vendor=vendor, brand=brand,
        frame_material=frame_material, drivetrain_groupset=drivetrain_groupset,
        min_discount=min_discount, min_price=min_price, max_price=max_price,
        q=q, added_since=added_since, sku=sku,
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
        br.sku_vendor_count = sku_vendor_counts.get(bike_obj.sku, 0) if bike_obj.sku else 0
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

    # Cross-shop offers: every in-stock listing of the same SKU, collapsed to the
    # cheapest variant per shop. No SKU → the bike stands alone.
    if primary.sku:
        rows = await db.execute(
            select(Bike)
            .where(Bike.sku == primary.sku, Bike.in_stock == True)  # noqa: E712
            .order_by(Bike.price_sale.asc())
        )
        candidates = rows.scalars().all()
    else:
        candidates = [primary] if primary.in_stock else []

    # Rows arrive price-ascending, so the first row seen per shop is its cheapest.
    cheapest_per_shop: dict[tuple[str, str], Bike] = {}
    for b in candidates:
        key = (b.vendor_name, b.city or "")
        if key not in cheapest_per_shop:
            cheapest_per_shop[key] = b

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
        )
        for b in sorted(cheapest_per_shop.values(), key=lambda x: x.price_sale)
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
    total_r         = await db.execute(select(func.count()).where(in_stock_clause))
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
