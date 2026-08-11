import asyncio
import logging
import random

import httpx

from scrapers.models import ScrapeResult, VendorConfig
from scrapers.pipelines.bigcommerce import scrape_bigcommerce
from scrapers.pipelines.canyon import scrape_canyon
from scrapers.pipelines.ecwid_next import scrape_ecwid_next
from scrapers.pipelines.giant import scrape_giant
from scrapers.pipelines.shopify import scrape_shopify
from scrapers.pipelines.woocommerce import scrape_woocommerce
from scrapers.pipelines.woocommerce_api import scrape_woocommerce_api
from scrapers.utils import redact_proxy

logger = logging.getLogger(__name__)


async def scrape_vendor(
    config: VendorConfig,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    *,
    startup_jitter: tuple[float, float] = (0.0, 0.0),
) -> ScrapeResult:
    async with sem:
        # Spread vendor start times so the concurrent workers don't fire their
        # first requests in a synchronised burst, which trips Cloudflare's
        # per-IP bot mitigation. Off by default so the single-vendor tester
        # (scrape_check) stays instant.
        if startup_jitter[1] > 0:
            await asyncio.sleep(random.uniform(*startup_jitter))
        try:
            if config.pipeline == "shopify":
                bikes, invalid_count = await scrape_shopify(config, client)
            elif config.pipeline == "woocommerce":
                bikes, invalid_count = await scrape_woocommerce(config, client)
            elif config.pipeline == "woocommerce_api":
                bikes, invalid_count = await scrape_woocommerce_api(config, client)
            elif config.pipeline == "ecwid_next":
                bikes, invalid_count = await scrape_ecwid_next(config, client)
            elif config.pipeline == "bigcommerce":
                bikes, invalid_count = await scrape_bigcommerce(config, client)
            elif config.pipeline == "giant":
                bikes, invalid_count = await scrape_giant(config, client)
            elif config.pipeline == "canyon":
                bikes, invalid_count = await scrape_canyon(config, client)
            else:
                raise NotImplementedError(f"Pipeline {config.pipeline!r} not implemented")
            return ScrapeResult(
                vendor_name=config.vendor_name,
                bikes=bikes,
                invalid_count=invalid_count,
            )
        except Exception as exc:
            # ScrapeResult.error travels into scrape_summary.json and the daily
            # email, so scrub the proxy endpoint out of it here — this is the
            # single boundary every vendor failure passes through.
            message = redact_proxy(str(exc))
            logger.error("[%s] Scrape failed: %s", config.vendor_name, message, exc_info=True)
            return ScrapeResult(vendor_name=config.vendor_name, bikes=[], error=message)
