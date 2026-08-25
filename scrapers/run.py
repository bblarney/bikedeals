import asyncio
import json
import logging
import os
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker

from scrapers.db import (
    get_engine,
    init_db,
    mark_stale,
    prune_price_events,
    upsert_bikes,
    write_scrape_log,
)
from scrapers.orchestrator import scrape_vendor
from scrapers.registry import load_registry
from scrapers.utils import redact_proxy

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Keep concurrency modest: bursts of parallel requests from one IP trip
# Cloudflare's bot mitigation, which then challenges (429) the rest of the run.
# Overridable so it can be tuned without a code change.
MAX_CONCURRENT_VENDORS = int(os.environ.get("MAX_CONCURRENT_VENDORS", "3"))

# After acquiring a concurrency slot, each vendor waits a random delay in this
# range before its first request, so the workers don't fire in lockstep.
VENDOR_STARTUP_JITTER = (0.5, 1.5)

# Quarantine threshold: if >5% of products fail validation we treat the run as
# corrupt (vendor schema likely changed) and skip the upsert + mark_stale so we
# don't poison the DB. The vendor stays unchanged until someone fixes it.
QUARANTINE_INVALID_RATIO = 0.05

# Price history is stored as change-events (one row per first-seen / price
# change). Old events are pruned daily so the table stays flat under the
# free-tier storage cap. Overridable without a code change.
PRICE_EVENT_RETENTION_DAYS = int(os.environ.get("PRICE_EVENT_RETENTION_DAYS", "365"))


class _LogCollector(logging.Handler):
    """Captures WARNING+ log records during a run.

    The daily email previously listed only per-vendor *failures*. This lets the
    summary surface every warning and error that came up (retries, robots.txt
    skips, category-map misses, validation issues, …) so problems that don't
    fail a whole vendor are still visible.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[tuple[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Belt and braces: these lines go out in the daily email, and this
            # handler catches records from third-party loggers (httpx, urllib3)
            # that never pass through our own redaction points.
            self.records.append((record.levelname, redact_proxy(record.getMessage())))
        except Exception:
            pass

    def grouped(self) -> list[dict]:
        """Identical (level, message) lines collapsed to one entry with a count,
        most frequent first."""
        counts = Counter(self.records)
        return [
            {"level": level, "message": message, "count": n}
            for (level, message), n in sorted(
                counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1])
            )
        ]


async def main() -> None:
    log_collector = _LogCollector()
    logging.getLogger().addHandler(log_collector)

    bad_rrp_by_reason: Counter = Counter()
    bad_rrp_by_vendor: Counter = Counter()

    vendors = load_registry()
    # Randomise order so the same vendors aren't always the ones scraped first
    # (and so no vendor is permanently starved if we get throttled mid-run).
    random.shuffle(vendors)
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
        # On Postgres (prod) Alembic owns the schema — `alembic upgrade head`
        # runs before this. Calling create_all here is what silently drifts the
        # DB out of Alembic's tracking: it adds new *tables* but never altered
        # columns/constraints, so the next model change desyncs prod. Restrict
        # create_all to SQLite, where it stays a zero-setup dev convenience.
        if engine.url.get_backend_name() == "sqlite":
            await init_db(engine)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    sem = asyncio.Semaphore(MAX_CONCURRENT_VENDORS)
    ok = failed = total_bikes = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = {
            asyncio.ensure_future(
                scrape_vendor(v, client, sem, startup_jitter=VENDOR_STARTUP_JITTER)
            ): v
            for v in vendors
        }

        for coro in asyncio.as_completed(tasks):
            result = await coro

            if result.implausible_rrp_count:
                bad_rrp_by_reason.update(result.implausible_rrp_reasons)
                bad_rrp_by_vendor[result.vendor_name] += result.implausible_rrp_count

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

            # A scrape that returns zero bikes is never trusted: we can't tell a
            # genuinely empty shop from a blocked/broken fetch, and running
            # mark_stale here would flag the vendor's *entire* existing inventory
            # out-of-stock on a transient failure. Treat it as failed and leave
            # yesterday's data untouched.
            if not result.bikes:
                msg = "scrape returned 0 bikes — treating as failed; existing data kept (mark_stale skipped)"
                logging.error("[%s] %s", result.vendor_name, msg)
                failures.append({"vendor": result.vendor_name, "error": msg})
                failed += 1
                if SessionLocal:
                    async with SessionLocal() as session:
                        await write_scrape_log(
                            session,
                            vendor_name=result.vendor_name,
                            run_at=run_start,
                            status="empty",
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

    if SessionLocal:
        async with SessionLocal() as session:
            removed = await prune_price_events(session, PRICE_EVENT_RETENTION_DAYS)
        if removed:
            logging.info(
                "Pruned %d price event(s) older than %d days",
                removed,
                PRICE_EVENT_RETENTION_DAYS,
            )

    if engine:
        await engine.dispose()

    logging.info("Done: %d vendor(s) ok, %d failed, %d total bikes upserted", ok, failed, total_bikes)

    warnings = log_collector.grouped()
    logging.getLogger().removeHandler(log_collector)

    summary = {
        "run_at": run_start.isoformat(),
        "duration_seconds": round(time.monotonic() - run_start_mono, 1),
        "vendors_total": len(vendors),
        "vendors_ok": ok,
        "vendors_failed": failed,
        "total_bikes_upserted": total_bikes,
        # Fabricated discounts we refused to publish. Visible every run: the
        # default sort is discount_desc, so a shop typo lands on the homepage.
        "implausible_rrp_dropped": sum(bad_rrp_by_reason.values()),
        "implausible_rrp_by_reason": dict(bad_rrp_by_reason.most_common()),
        "implausible_rrp_by_vendor": dict(bad_rrp_by_vendor.most_common(10)),
        "failures": failures,
        "warnings": warnings,
    }
    Path("scrape_summary.json").write_text(json.dumps(summary, indent=2))
    logging.info("Summary written to scrape_summary.json")


if __name__ == "__main__":
    asyncio.run(main())
