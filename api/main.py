import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models import Bike, ScrapeLog
from api.schemas import BikeResponse, FiltersResponse, PaginatedBikes

app = FastAPI(title="BikeGrid API", version="1.0")

_default_origins = "https://bikegrid.com.au,https://www.bikegrid.com.au"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_SORT_COLUMNS = {
    "discount_desc": Bike.discount_percentage.desc(),
    "price_asc": Bike.price_sale.asc(),
    "price_desc": Bike.price_sale.desc(),
    "clicks_desc": Bike.click_count.desc(),
}

CACHE_BIKES = "max-age=300"   # 5 min — bikes update after each scrape run
CACHE_FILTERS = "max-age=60"  # 1 min — filters change when vendors are added

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
    min_discount: int,
    q: str | None,
    added_since: str | None,
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
    if min_discount > 0:
        query = query.where(Bike.discount_percentage >= min_discount)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            func.lower(Bike.brand).like(pattern)
            | func.lower(Bike.model_name).like(pattern)
        )
    if added_since:
        query = query.where(Bike.scraped_at >= _added_since_cutoff(added_since))
    return query


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/bikes", response_model=PaginatedBikes)
async def get_bikes(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    category: list[str] = Query(default=[]),
    city: list[str] = Query(default=[]),
    size: list[str] = Query(default=[]),
    vendor: list[str] = Query(default=[]),
    brand: list[str] = Query(default=[]),
    min_discount: int = Query(default=0, ge=0, le=100),
    in_stock: bool = True,
    q: str | None = None,
    sort: str = Query(default="discount_desc", pattern="^(discount_desc|price_asc|price_desc|clicks_desc)$"),
    added_since: str | None = Query(default=None, pattern="^(day|week|month|year)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    base = select(Bike)
    base = _apply_filters(
        base,
        city=city, category=category, size=size, vendor=vendor, brand=brand,
        min_discount=min_discount, q=q, added_since=added_since,
    )
    if in_stock:
        base = base.where(Bike.in_stock == True)  # noqa: E712

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()

    order_col = _SORT_COLUMNS.get(sort, Bike.discount_percentage.desc())
    rows = await db.execute(base.order_by(order_col).limit(limit).offset(offset))
    bikes = rows.scalars().all()

    response.headers["Cache-Control"] = CACHE_BIKES
    return PaginatedBikes(
        total=total,
        limit=limit,
        offset=offset,
        results=[BikeResponse.model_validate(b) for b in bikes],
    )


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
async def get_filters(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    category: list[str] = Query(default=[]),
    city: list[str] = Query(default=[]),
    size: list[str] = Query(default=[]),
    vendor: list[str] = Query(default=[]),
    brand: list[str] = Query(default=[]),
    min_discount: int = Query(default=0, ge=0, le=100),
    q: str | None = None,
    added_since: str | None = Query(default=None, pattern="^(day|week|month|year)$"),
):
    # Faceted filters: each facet's options are computed with all *other* active
    # filters applied (the facet excludes itself). That keeps each list relevant
    # without trapping the user in a single-option facet.
    f = dict(
        city=city, category=category, size=size, vendor=vendor, brand=brand,
        min_discount=min_discount, q=q, added_since=added_since,
    )

    def facet_query(col, ignored: str):
        base = select(col).distinct().where(Bike.in_stock == True).order_by(col)  # noqa: E712
        overrides = f.copy()
        overrides[ignored] = [] if isinstance(f[ignored], list) else (0 if ignored == "min_discount" else None)
        return _apply_filters(base, **overrides)

    # NOTE: SQLAlchemy's async session serializes within a single connection,
    # so asyncio.gather here would raise InvalidRequestError. Real concurrency
    # needs separate sessions from the pool; that's a larger refactor.
    in_stock_clause = Bike.in_stock == True  # noqa: E712
    categories_r    = await db.execute(facet_query(Bike.category,    "category"))
    cities_r        = await db.execute(facet_query(Bike.city,        "city"))
    sizes_r         = await db.execute(facet_query(Bike.frame_size,  "size"))
    vendors_r       = await db.execute(facet_query(Bike.vendor_name, "vendor"))
    brands_r        = await db.execute(facet_query(Bike.brand,       "brand"))
    discount_r      = await db.execute(select(func.min(Bike.discount_percentage), func.max(Bike.discount_percentage)).where(in_stock_clause))
    total_r         = await db.execute(select(func.count()).where(in_stock_clause))
    last_scraped_r  = await db.execute(select(func.max(ScrapeLog.run_at)).where(ScrapeLog.status == "ok"))
    discount_row = discount_r.one()

    response.headers["Cache-Control"] = CACHE_FILTERS

    return FiltersResponse(
        categories=[r[0] for r in categories_r.all()],
        cities=[r[0] for r in cities_r.all()],
        sizes=[r[0] for r in sizes_r.all()],
        vendors=[r[0] for r in vendors_r.all()],
        brands=[r[0] for r in brands_r.all()],
        discount_range={"min": discount_row[0] or 0, "max": discount_row[1] or 0},
        total_bikes=total_r.scalar_one(),
        last_scraped_at=last_scraped_r.scalar_one(),
    )
