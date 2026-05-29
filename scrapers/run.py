import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

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
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

MAX_CONCURRENT_VENDORS = 5

# Quarantine threshold: if >5% of products fail validation we treat the run as
# corrupt (vendor schema likely changed) and skip the upsert + mark_stale so we
# don't poison the DB. The vendor stays unchanged until someone fixes it.
QUARANTINE_INVALID_RATIO = 0.05


async def main() -> None:
    vendors = load_registry()
    logging.info("Loaded %d vendor(s)", len(vendors))

    run_start = datetime.now(timezone.utc)
    run_start_mono = time.monotonic()
    failures: list[dict] = []

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
    ok = failed = total_bikes = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = {asyncio.ensure_future(scrape_vendor(v, client, sem)): v for v in vendors}

        for coro in asyncio.as_completed(tasks):
            result = await coro

            if result.error:
                logging.error("Vendor %r failed: %s", result.vendor_name, result.error)
                failures.append({"vendor": result.vendor_name, "error": result.error})
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
                continue

            seen = len(result.bikes) + result.invalid_count
            invalid_ratio = result.invalid_count / seen if seen else 0.0
            if seen > 0 and invalid_ratio > QUARANTINE_INVALID_RATIO:
                msg = (
                    f"{result.invalid_count}/{seen} products failed validation "
                    f"({invalid_ratio:.1%} > {QUARANTINE_INVALID_RATIO:.0%}) — quarantining"
                )
                logging.error("[%s] %s", result.vendor_name, msg)
                failures.append({"vendor": result.vendor_name, "error": msg})
                failed += 1
                if SessionLocal:
                    async with SessionLocal() as session:
                        await write_scrape_log(
                            session,
                            vendor_name=result.vendor_name,
                            run_at=run_start,
                            status="quarantined",
                            error_msg=msg,
                        )
                continue

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
                total_bikes += count
                logging.info("[%s] Upserted %d bikes", result.vendor_name, count)

    if engine:
        await engine.dispose()

    logging.info("Done: %d vendor(s) ok, %d failed, %d total bikes upserted", ok, failed, total_bikes)

    summary = {
        "run_at": run_start.isoformat(),
        "duration_seconds": round(time.monotonic() - run_start_mono, 1),
        "vendors_total": len(vendors),
        "vendors_ok": ok,
        "vendors_failed": failed,
        "total_bikes_upserted": total_bikes,
        "failures": failures,
    }
    Path("scrape_summary.json").write_text(json.dumps(summary, indent=2))
    logging.info("Summary written to scrape_summary.json")


if __name__ == "__main__":
    asyncio.run(main())
