import asyncio
import logging
import random

import httpx

from scrapers.models import ScrapeResult, VendorConfig
from scrapers.pipelines.bigcommerce import scrape_bigcommerce
from scrapers.pipelines.canyon import scrape_canyon
from scrapers.pipelines.giant import scrape_giant
from scrapers.pipelines.lightspeed import scrape_lightspeed
from scrapers.pipelines.shopify import scrape_shopify
from scrapers.pipelines.woocommerce import scrape_woocommerce
from scrapers.pipelines.woocommerce_api import scrape_woocommerce_api
from scrapers.price_sanity import drop_implausible_rrp
from scrapers.product_filter import drop_non_bikes
from scrapers.utils import redact_proxy

logger = logging.getLogger(__name__)

# Pipeline name (the YAML's `pipeline:` value) to its scraper. Every entry
# shares one signature: (config, client) -> (bikes, invalid_count).
_PIPELINES = {
    "shopify": scrape_shopify,
    "woocommerce": scrape_woocommerce,
    "woocommerce_api": scrape_woocommerce_api,
    "bigcommerce": scrape_bigcommerce,
    "giant": scrape_giant,
    "lightspeed": scrape_lightspeed,
    "canyon": scrape_canyon,
}


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
            scrape = _PIPELINES.get(config.pipeline)
            if scrape is None:
                raise NotImplementedError(f"Pipeline {config.pipeline!r} not implemented")
            bikes, invalid_count = await scrape(config, client)
            # Every pipeline funnels through here, so both post-scrape passes
            # live at this single boundary rather than in six places.
            #
            # Order matters. The not-a-bike gate runs first, so the RRP check
            # only ever compares real bikes against each other: an accessory
            # sharing a bike's model name would otherwise drag the sibling
            # median down and cast suspicion on the bike.
            bikes, non_bike_reasons = drop_non_bikes(bikes)
            non_bike_count = sum(non_bike_reasons.values())
            if non_bike_count:
                logger.info(
                    "[%s] Dropped %d non-bike listing(s): %s",
                    config.vendor_name,
                    non_bike_count,
                    ", ".join(f"{r}={n}" for r, n in sorted(non_bike_reasons.items())),
                )
            bikes, bad_rrp = drop_implausible_rrp(bikes)
            if bad_rrp:
                logger.info(
                    "[%s] Dropped %d implausible RRP(s): %s",
                    config.vendor_name, sum(bad_rrp.values()),
                    ", ".join(f"{r}={n}" for r, n in sorted(bad_rrp.items())),
                )
            return ScrapeResult(
                vendor_name=config.vendor_name,
                bikes=bikes,
                invalid_count=invalid_count,
                non_bike_count=non_bike_count,
                non_bike_reasons=non_bike_reasons,
                implausible_rrp_count=sum(bad_rrp.values()),
                implausible_rrp_reasons=bad_rrp,
            )
        except Exception as exc:
            # ScrapeResult.error travels into scrape_summary.json and the daily
            # email, so scrub the proxy endpoint out of it here — this is the
            # single boundary every vendor failure passes through.
            message = redact_proxy(str(exc))
            logger.error("[%s] Scrape failed: %s", config.vendor_name, message, exc_info=True)
            return ScrapeResult(vendor_name=config.vendor_name, bikes=[], error=message)
