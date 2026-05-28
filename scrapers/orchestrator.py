import asyncio
import logging

import httpx

from scrapers.models import ScrapeResult, VendorConfig
from scrapers.pipelines.bigcommerce import scrape_bigcommerce
from scrapers.pipelines.giant import scrape_giant
from scrapers.pipelines.shopify import scrape_shopify
from scrapers.pipelines.woocommerce import scrape_woocommerce

logger = logging.getLogger(__name__)


async def scrape_vendor(
    config: VendorConfig, client: httpx.AsyncClient, sem: asyncio.Semaphore
) -> ScrapeResult:
    async with sem:
        try:
            if config.pipeline == "shopify":
                bikes, invalid_count = await scrape_shopify(config, client)
            elif config.pipeline == "woocommerce":
                bikes, invalid_count = await scrape_woocommerce(config, client)
            elif config.pipeline == "bigcommerce":
                bikes, invalid_count = await scrape_bigcommerce(config, client)
            elif config.pipeline == "giant":
                bikes, invalid_count = await scrape_giant(config, client)
            else:
                raise NotImplementedError(f"Pipeline {config.pipeline!r} not implemented")
            return ScrapeResult(
                vendor_name=config.vendor_name,
                bikes=bikes,
                invalid_count=invalid_count,
            )
        except Exception as exc:
            logger.error("[%s] Scrape failed: %s", config.vendor_name, exc, exc_info=True)
            return ScrapeResult(vendor_name=config.vendor_name, bikes=[], error=str(exc))
