from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Response

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models import Bike, ScrapeLog
from api.schemas import BikeResponse, FiltersResponse, PaginatedBikes

app = FastAPI(title="Bikedeals API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_SORT_COLUMNS = {
    "discount_desc": Bike.discount_percentage.desc(),
    "price_asc": Bike.price_sale.asc(),
    "price_desc": Bike.price_sale.desc(),
    "clicks_desc": Bike.click_count.desc(),
}

CACHE_BIKES = "max-age=300"   # 5 min — bikes update after each scrape run
CACHE_FILTERS = "max-age=60"  # 1 min — filters change when vendors are added


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
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    base = select(Bike)

    if category:
        base = base.where(Bike.category.in_(category))
    if city:
        base = base.where(func.lower(Bike.city).in_([c.lower() for c in city]))
    if size:
        base = base.where(Bike.frame_size.in_(size))
    if vendor:
        base = base.where(Bike.vendor_name.in_(vendor))
    if brand:
        base = base.where(Bike.brand.in_(brand))
    if min_discount > 0:
        base = base.where(Bike.discount_percentage >= min_discount)
    if in_stock:
        base = base.where(Bike.in_stock == True)  # noqa: E712
    if q:
        base = base.where(
            (Bike.brand + " " + Bike.model_name).ilike(f"%{q}%")
        )

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
async def record_click(
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
):
    categories_r = await db.execute(
        select(Bike.category).distinct().order_by(Bike.category)
    )
    cities_r = await db.execute(
        select(Bike.city).distinct().order_by(Bike.city)
    )
    sizes_r = await db.execute(
        select(Bike.frame_size).distinct().order_by(Bike.frame_size)
    )
    vendors_r = await db.execute(
        select(Bike.vendor_name).distinct().order_by(Bike.vendor_name)
    )
    brands_r = await db.execute(
        select(Bike.brand).distinct().order_by(Bike.brand)
    )
    discount_r = await db.execute(
        select(func.min(Bike.discount_percentage), func.max(Bike.discount_percentage))
    )
    total_r = await db.execute(select(func.count()).where(Bike.in_stock == True))  # noqa: E712
    last_scraped_r = await db.execute(
        select(func.max(ScrapeLog.run_at)).where(ScrapeLog.status == "ok")
    )

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
