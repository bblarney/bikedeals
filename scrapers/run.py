import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker

from scrapers.db import get_engine, init_db, mark_stale, upsert_bikes, write_scrape_log
from scrapers.orchestrator import scrape_vendor
from scrapers.registry import load_registry

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

MAX_CONCURRENT_VENDORS = 5


async def main() -> None:
    vendors = load_registry()
    logging.info("Loaded %d vendor(s)", len(vendors))

    run_start = datetime.now(timezone.utc)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logging.info("DATABASE_URL not set — skipping DB writes")

    engine = None
    SessionLocal = None
    if database_url:
        engine = await get_engine(database_url)
        await init_db(engine)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    sem = asyncio.Semaphore(MAX_CONCURRENT_VENDORS)
    ok = failed = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = {asyncio.ensure_future(scrape_vendor(v, client, sem)): v for v in vendors}

        for coro in asyncio.as_completed(tasks):
            result = await coro

            if result.error:
                logging.error("Vendor %r failed: %s", result.vendor_name, result.error)
                failed += 1
                if SessionLocal:
                    async with SessionLocal() as session:
                        await write_scrape_log(
                            session,
                            vendor_name=result.vendor_name,
                            run_at=run_start,
                            status="quarantined",
                            error_msg=result.error,
                        )
            else:
                ok += 1
                if SessionLocal:
                    async with SessionLocal() as session:
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

    if engine:
        await engine.dispose()

    logging.info("Done: %d successful vendor(s), %d failed", ok, failed)


if __name__ == "__main__":
    asyncio.run(main())
