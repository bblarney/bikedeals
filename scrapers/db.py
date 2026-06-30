from datetime import datetime, timedelta, timezone

from sqlalchemy import case, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from api.models import Base, Bike, PriceEvent, ScrapeLog
from scrapers.models import BikeRecord


async def get_engine(url: str):
    return create_async_engine(url)


async def init_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


_CHUNK_SIZE = 1000


def price_event_rows(
    records: list[BikeRecord], prior: dict[str, float]
) -> list[dict]:
    """Pick the records that warrant a new price change-event.

    A record qualifies if it is new (``prior`` miss — a seed anchor point) or
    its sale price moved. Prices are compared in whole cents so float wobble
    never registers as a change.
    """
    return [
        {
            "bike_id": r.id,
            "price_sale": r.price_sale,
            "price_original": r.price_original,
            "observed_at": r.last_seen_at,
        }
        for r in records
        if r.id not in prior
        or round(r.price_sale * 100) != round(prior[r.id] * 100)
    ]


async def upsert_bikes(session: AsyncSession, records: list[BikeRecord]) -> int:
    if not records:
        return 0
    deduped = list({r.id: r for r in records}.values())
    for i in range(0, len(deduped), _CHUNK_SIZE):
        chunk = deduped[i : i + _CHUNK_SIZE]

        # Capture stored sale prices *before* the upsert overwrites them, so we
        # can tell which listings are new or have actually changed price.
        prior_rows = await session.execute(
            select(Bike.id, Bike.price_sale).where(
                Bike.id.in_([r.id for r in chunk])
            )
        )
        prior = dict(prior_rows.all())

        stmt = pg_insert(Bike).values([r.model_dump() for r in chunk])
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                # Pricing & stock change on every scrape
                "price_sale": stmt.excluded.price_sale,
                "price_original": stmt.excluded.price_original,
                "discount_percentage": stmt.excluded.discount_percentage,
                "in_stock": stmt.excluded.in_stock,
                "last_seen_at": stmt.excluded.last_seen_at,
                # Catalog details can change too: shops re-categorise, rename,
                # or update images. Refresh them so the DB reflects the source.
                # scraped_at is intentionally omitted to preserve first-seen.
                "category": stmt.excluded.category,
                "brand": stmt.excluded.brand,
                "model_name": stmt.excluded.model_name,
                "frame_size": stmt.excluded.frame_size,
                "image_url": stmt.excluded.image_url,
                "product_url": stmt.excluded.product_url,
                "sku": stmt.excluded.sku,
                "weight_grams": stmt.excluded.weight_grams,
                "product_updated_at": stmt.excluded.product_updated_at,
                "tags": stmt.excluded.tags,
                "frame_material": stmt.excluded.frame_material,
                "drivetrain_groupset": stmt.excluded.drivetrain_groupset,
                # Set price_drop_at when sale price decreases; preserve existing otherwise.
                "price_drop_at": case(
                    (stmt.excluded.price_sale < Bike.price_sale, stmt.excluded.last_seen_at),
                    else_=Bike.price_drop_at,
                ),
                # Set discount_started_at when a discount appears for the first time.
                "discount_started_at": case(
                    (
                        (Bike.discount_percentage == 0) & (stmt.excluded.discount_percentage > 0),
                        stmt.excluded.last_seen_at,
                    ),
                    else_=Bike.discount_started_at,
                ),
            },
        )
        await session.execute(stmt)

        # Append a price change-event for each new/changed listing. Only
        # currently-scraped listings get events, so the table grows with real
        # price activity rather than as a daily snapshot.
        events = price_event_rows(chunk, prior)
        if events:
            await session.execute(pg_insert(PriceEvent).values(events))
    await session.commit()
    return len(deduped)


async def prune_price_events(session: AsyncSession, max_age_days: int) -> int:
    """Delete price events older than ``max_age_days`` to keep the table flat.

    Returns the number of rows removed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    result = await session.execute(
        delete(PriceEvent).where(PriceEvent.observed_at < cutoff)
    )
    await session.commit()
    return result.rowcount or 0


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
    stmt = pg_insert(ScrapeLog).values(
        vendor_name=vendor_name,
        run_at=run_at,
        status=status,
        bikes_upserted=bikes_upserted,
        error_msg=error_msg,
        last_success_at=run_at if status == "ok" else None,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["vendor_name"],
        set_={
            "run_at": stmt.excluded.run_at,
            "status": stmt.excluded.status,
            "bikes_upserted": stmt.excluded.bikes_upserted,
            "error_msg": stmt.excluded.error_msg,
            # Advance only on success; otherwise preserve prior success time.
            "last_success_at": case(
                (stmt.excluded.status == "ok", stmt.excluded.run_at),
                else_=ScrapeLog.last_success_at,
            ),
        },
    )
    await session.execute(stmt)
    await session.commit()
