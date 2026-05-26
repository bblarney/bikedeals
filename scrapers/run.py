import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker

from scrapers.db import get_engine, init_db, mark_stale, upsert_bikes, write_scrape_log
from scrapers.orchestrator import run_all
from scrapers.registry import load_registry

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def main() -> None:
    vendors = load_registry()
    logging.info("Loaded %d vendor(s)", len(vendors))

    run_start = datetime.now(timezone.utc)
    results = await run_all(vendors)

    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]

    for r in failed:
        logging.error("Vendor %r failed: %s", r.vendor_name, r.error)

    # Phase 1: always write JSON for inspection
    output = [r.model_dump(mode="json") for r in successful]
    Path("output.json").write_text(json.dumps(output, indent=2, default=str))
    logging.info("output.json written with %d vendor result(s)", len(successful))

    # Phase 2: write to DB when DATABASE_URL is configured
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logging.info("DATABASE_URL not set — skipping DB writes")
        return

    engine = await get_engine(database_url)
    await init_db(engine)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as session:
        for result in successful:
            count = await upsert_bikes(session, result.bikes)
            await mark_stale(session, result.vendor_name, run_start)
            await write_scrape_log(
                session,
                vendor_name=result.vendor_name,
                run_at=run_start,
                status="ok",
                bikes_upserted=count,
            )
            logging.info("[%s] Upserted %d bikes", result.vendor_name, count)

        for result in failed:
            await write_scrape_log(
                session,
                vendor_name=result.vendor_name,
                run_at=run_start,
                status="quarantined",
                error_msg=result.error,
            )

    await engine.dispose()
    logging.info(
        "Done: %d successful vendor(s), %d failed",
        len(successful),
        len(failed),
    )


if __name__ == "__main__":
    asyncio.run(main())
