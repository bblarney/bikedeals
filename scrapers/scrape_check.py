"""Lightweight single-vendor scrape tester — no database required.

Runs the production scrape pipeline for ONE shop and prints a report, so a new
vendor YAML can be verified before it ever goes into a real run. Nothing is
written to any database; this only fetches and parses.

Usage:
    python -m scrapers.scrape_check <vendor>
    python -m scrapers.scrape_check hendrys --samples 20
    python -m scrapers.scrape_check driftbikes --max-pages 1   # quick check
    python -m scrapers.scrape_check "Crooze" --json > result.json

<vendor> matches the YAML's vendor_name ignoring case, spaces and punctuation,
so "Hendry's", "hendrys" and "HENDRYS" all resolve to the same shop.

Exit code is 0 when the scrape would pass production's checks, 1 otherwise
(scrape error, too many invalid records, or zero bikes) — so it is usable in CI
or a pre-commit check.
"""
import argparse
import asyncio
import json
import logging
import re
import statistics
import sys
from collections import Counter

import httpx

from scrapers.models import VendorConfig
from scrapers.orchestrator import scrape_vendor
from scrapers.registry import load_registry
# Reuse the exact threshold production uses to quarantine a vendor, so this
# tester's verdict mirrors what a real run would decide.
from scrapers.run import QUARANTINE_INVALID_RATIO


def _normalize(name: str) -> str:
    """Lowercase and strip everything but letters/digits for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find_vendor(registry: list[VendorConfig], query: str) -> VendorConfig:
    """Resolve a CLI query to exactly one VendorConfig.

    Matches on the normalized vendor_name: exact first, then unique substring.
    Raises LookupError (listing options) if there's no match or it's ambiguous.
    """
    q = _normalize(query)
    exact = [v for v in registry if _normalize(v.vendor_name) == q]
    if len(exact) == 1:
        return exact[0]

    partial = [v for v in registry if q and q in _normalize(v.vendor_name)]
    if len(partial) == 1:
        return partial[0]

    if len(partial) > 1:
        names = ", ".join(sorted(v.vendor_name for v in partial))
        raise LookupError(f"{query!r} is ambiguous — matches: {names}")

    available = ", ".join(sorted(v.vendor_name for v in registry))
    raise LookupError(f"No vendor matches {query!r}. Available: {available}")


def _print_report(config: VendorConfig, result, samples: int) -> None:
    bikes = result.bikes
    location = config.city or (f"{len(config.cities)} cities" if config.cities else "—")
    print(f"\n=== {config.vendor_name} ===")
    print(f"  pipeline : {config.pipeline}")
    print(f"  location : {location}")
    print(f"  base_url : {config.base_url}")

    if result.error:
        print(f"\n  RESULT   : scrape raised an error\n  ERROR    : {result.error}")
        return

    seen = len(bikes) + result.invalid_count
    ratio = result.invalid_count / seen if seen else 0.0
    unique_products = len({b.product_url.split("?")[0] for b in bikes})
    print("\n  counts")
    print(f"    bikes (variants) : {len(bikes)}")
    print(f"    unique products  : {unique_products}")
    print(f"    invalid records  : {result.invalid_count} ({ratio:.1%} of {seen} seen)")

    if not bikes:
        return

    cats = Counter(b.category for b in bikes)
    brands = Counter(b.brand for b in bikes)
    prices = [b.price_sale for b in bikes]
    in_stock = sum(1 for b in bikes if b.in_stock)
    discounted = sum(1 for b in bikes if b.discount_percentage > 0)
    no_image = sum(1 for b in bikes if not b.image_url)
    no_size = sum(1 for b in bikes if b.frame_size == "N/A")

    print("\n  breakdown")
    print(f"    categories : {dict(cats)}")
    print(f"    top brands : {dict(brands.most_common(10))}")
    print(f"    price $    : min {min(prices):.0f} / median {statistics.median(prices):.0f} / max {max(prices):.0f}")
    print(f"    in stock   : {in_stock}/{len(bikes)}")
    print(f"    discounted : {discounted}/{len(bikes)}")

    print("\n  data quality")
    print(f"    missing image : {no_image}")
    print(f"    no frame size : {no_size}")
    if len(cats) == 1:
        print(f"    NOTE: every bike resolved to a single category ({next(iter(cats))}) — check category_map")

    print(f"\n  samples (first {min(samples, len(bikes))})")
    for b in bikes[:samples]:
        orig = f"${b.price_original:.0f}" if b.price_original else "-"
        print(
            f"    [{b.category:8}] {b.brand} {b.model_name} | size={b.frame_size} "
            f"| ${b.price_sale:.0f} (was {orig}, -{b.discount_percentage}%)"
        )


def _verdict(result) -> tuple[str, int]:
    """Mirror production's per-vendor decision. Returns (label, exit_code)."""
    if result.error:
        return "FAIL — scrape errored (would be quarantined)", 1
    seen = len(result.bikes) + result.invalid_count + result.non_bike_count
    ratio = result.invalid_count / seen if seen else 0.0
    if seen > 0 and ratio > QUARANTINE_INVALID_RATIO:
        return (
            f"FAIL — {ratio:.1%} invalid > {QUARANTINE_INVALID_RATIO:.0%} threshold "
            "(would be quarantined)",
            1,
        )
    if not result.bikes:
        return "FAIL — 0 bikes scraped (check collections / category_map / selectors)", 1
    return "PASS", 0


async def _run(config: VendorConfig) -> object:
    sem = asyncio.Semaphore(1)
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await scrape_vendor(config, client, sem)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scrapers.scrape_check",
        description="Run the production scrape pipeline for one vendor (no DB).",
    )
    parser.add_argument("vendor", help="vendor name (e.g. hendrys, \"Crooze\")")
    parser.add_argument("-n", "--samples", type=int, default=10, help="sample bikes to print (default 10)")
    parser.add_argument("--max-pages", type=int, default=None, help="override max_pages for a quick check")
    parser.add_argument("--json", action="store_true", help="emit JSON to stdout instead of a report")
    args = parser.parse_args(argv)

    # Logs (scrape progress) go to stderr, keeping stdout clean for --json.
    logging.basicConfig(
        level=logging.WARNING if args.json else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    try:
        config = find_vendor(load_registry(), args.vendor)
    except LookupError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.max_pages is not None:
        config.max_pages = args.max_pages

    result = asyncio.run(_run(config))
    label, code = _verdict(result)

    if args.json:
        json.dump(
            {
                "vendor_name": config.vendor_name,
                "pipeline": config.pipeline,
                "verdict": label,
                "passed": code == 0,
                "bike_count": len(result.bikes),
                "invalid_count": result.invalid_count,
                "non_bike_count": result.non_bike_count,
                "non_bike_reasons": result.non_bike_reasons,
                "error": result.error,
                "bikes": [b.model_dump(mode="json") for b in result.bikes],
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        _print_report(config, result, args.samples)
        print(f"\n  RESULT   : {label}\n")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
