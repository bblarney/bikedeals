import asyncio
import logging

import httpx

from scrapers.models import ScrapeResult, VendorConfig
from scrapers.pipelines.shopify import scrape_shopify
from scrapers.pipelines.woocommerce import scrape_woocommerce

logger = logging.getLogger(__name__)

MAX_CONCURRENT_VENDORS = 5


async def run_all(vendors: list[VendorConfig]) -> list[ScrapeResult]:
    sem = asyncio.Semaphore(MAX_CONCURRENT_VENDORS)
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [scrape_vendor(v, client, sem) for v in vendors]
        return await asyncio.gather(*tasks)


async def scrape_vendor(
    config: VendorConfig, client: httpx.AsyncClient, sem: asyncio.Semaphore
) -> ScrapeResult:
    async with sem:
        try:
            if config.pipeline == "shopify":
                bikes = await scrape_shopify(config, client)
            elif config.pipeline == "woocommerce":
                bikes = await scrape_woocommerce(config, client)
            else:
                raise NotImplementedError(f"Pipeline {config.pipeline!r} not implemented")
            logger.info("[%s] Scraped %d bikes", config.vendor_name, len(bikes))
            return ScrapeResult(vendor_name=config.vendor_name, bikes=bikes)
        except Exception as exc:
            logger.error("[%s] Scrape failed: %s", config.vendor_name, exc, exc_info=True)
            return ScrapeResult(vendor_name=config.vendor_name, bikes=[], error=str(exc))
