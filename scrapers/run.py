import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from scrapers.orchestrator import run_all
from scrapers.registry import load_registry

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

if __name__ == "__main__":
    vendors = load_registry()
    logging.info("Loaded %d vendor(s)", len(vendors))

    results = asyncio.run(run_all(vendors))

    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]

    for r in failed:
        logging.error("Vendor %r failed: %s", r.vendor_name, r.error)

    output = [r.model_dump(mode="json") for r in successful]
    Path("output.json").write_text(json.dumps(output, indent=2, default=str))
    logging.info(
        "Done: %d successful vendor(s), %d failed. Output written to output.json",
        len(successful),
        len(failed),
    )
