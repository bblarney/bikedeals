from datetime import datetime

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from api.models import Base, Bike, ScrapeLog
from scrapers.models import BikeRecord


async def get_engine(url: str):
    return create_async_engine(url)


async def init_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def upsert_bikes(session: AsyncSession, records: list[BikeRecord]) -> int:
    if not records:
        return 0
    for r in records:
        data = r.model_dump()
        stmt = pg_insert(Bike).values(**data).on_conflict_do_update(
            index_elements=["id"],
            set_={
                "price_sale": r.price_sale,
                "price_original": r.price_original,
                "discount_percentage": r.discount_percentage,
                "in_stock": r.in_stock,
                "last_seen_at": r.last_seen_at,
            },
        )
        await session.execute(stmt)
    await session.commit()
    return len(records)


async def mark_stale(
    session: AsyncSession, vendor_name: str, run_start: datetime
) -> None:
    await session.execute(
        update(Bike)
        .where(Bike.vendor_name == vendor_name, Bike.last_seen_at < run_start)
        .values(in_stock=False)
    )
    await session.commit()


async def write_scrape_log(
    session: AsyncSession,
    vendor_name: str,
    run_at: datetime,
    status: str,
    bikes_upserted: int = 0,
    error_msg: str | None = None,
) -> None:
    log = ScrapeLog(
        vendor_name=vendor_name,
        run_at=run_at,
        status=status,
        bikes_upserted=bikes_upserted,
        error_msg=error_msg,
    )
    session.add(log)
    await session.commit()
