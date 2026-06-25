import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from scrapers.config import SCRAPER_DELAY_RANGE, SCRAPER_USER_AGENT
from scrapers.models import BikeRecord, VendorConfig, compute_discount, make_bike_id
from scrapers.utils import CloudflareChallenge, check_robots, get_with_retry, parse_price, resolve_category

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"\$([\d,]+(?:\.\d{2})?)")


def _extract_giant_price(text: str) -> float | None:
    """Parse a price from 'Current price:$14,999 RRP' style text."""
    m = _PRICE_RE.search(text)
    if not m:
        return None
    return parse_price(m.group(1))


async def scrape_giant(config: VendorConfig, client: httpx.AsyncClient) -> tuple[list[BikeRecord], int]:
    """Scrape Giant Bicycles franchise CMS stores.

    These stores run Giant's proprietary brand platform (Cloudinary CDN). Each
    store has multiple category pages; set shop_paths to the list of paths to
    scrape (e.g. ['au/bikes/road-bikes', 'au/bikes/mountain-bikes', ...]).
    Products that appear on more than one page are deduplicated by URL.
    """
    if not await check_robots(config.base_url, client):
        logger.warning("[%s] Skipping — disallowed by robots.txt", config.vendor_name)
        return [], 0

    logger.info("[%s] Scraping...", config.vendor_name)
    headers = {"User-Agent": SCRAPER_USER_AGENT}
    now = datetime.now(timezone.utc)

    paths = config.shop_paths or [config.shop_path]
    seen_urls: set[str] = set()
    bikes: list[BikeRecord] = []
    invalid_count = 0

    for path in paths:
        url = f"{config.base_url}/{path.strip('/')}/"
        try:
            resp = await get_with_retry(client, url, headers=headers)
            resp.raise_for_status()
        except CloudflareChallenge:
            raise  # not transient — abort the vendor so its data is preserved
        except Exception as exc:
            logger.error("[%s] Failed to fetch %s: %s", config.vendor_name, path, exc)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        products = soup.select("div.tile.product")

        if not products:
            logger.debug("[%s] No products found at %s", config.vendor_name, path)
            continue

        for item in products:
            article = item.select_one("div.article")
            if not article:
                continue

            link = article.select_one("a.textlink")
            if not link:
                continue

            caption = link.select_one("div.caption")
            if not caption:
                continue

            title_el = caption.select_one("div.h3")
            model_name = title_el.get_text(strip=True) if title_el else ""
            if not model_name:
                continue

            price_el = caption.select_one("p.prices")
            price_text = price_el.get_text(strip=True) if price_el else ""
            price_sale = _extract_giant_price(price_text)
            if price_sale is None or price_sale <= 0:
                logger.debug("[%s] Skipping product with no price: %r", config.vendor_name, model_name)
                continue

            raw_href = link.get("href", "")
            product_url = urljoin(config.base_url, raw_href) if raw_href else ""
            if not product_url or product_url in seen_urls:
                continue
            seen_urls.add(product_url)

            img_el = item.select_one("div.image img")
            image_url = img_el.get("src") if img_el else None

            # Derive category from surface-* CSS classes on the product wrapper,
            # falling back to model name. E-bike classes contain "electric" and
            # must match before the broader type classes.
            surface_tags = [
                cls.replace("surface-", "")
                for cls in item.get("class", [])
                if cls.startswith("surface-")
            ]
            category = resolve_category([model_name.lower()] + surface_tags, config.category_map)
            if category is None:
                logger.debug("[%s] No category match for %r; skipping", config.vendor_name, model_name)
                continue

            brand = config.vendor_name
            if config.brand_map:
                brand_tags = [
                    cls.replace("brand-", "")
                    for cls in item.get("class", [])
                    if cls.startswith("brand-")
                ]
                for tag in brand_tags:
                    if tag in config.brand_map:
                        brand = config.brand_map[tag]
                        break

            discount = compute_discount(price_sale, None)
            bike_id = make_bike_id(config.vendor_name, product_url, "One Size", config.city)

            try:
                record = BikeRecord(
                    id=bike_id,
                    vendor_name=config.vendor_name,
                    city=config.city,
                    brand=brand,
                    model_name=model_name,
                    category=category,
                    frame_size="One Size",
                    price_original=None,
                    price_sale=price_sale,
                    discount_percentage=discount,
                    in_stock=True,
                    product_url=product_url,
                    image_url=image_url,
                    scraped_at=now,
                    last_seen_at=now,
                )
                bikes.append(record)
            except Exception as exc:
                invalid_count += 1
                logger.warning("[%s] Validation error for %r: %s", config.vendor_name, model_name, exc)

        if len(paths) > 1:
            await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))

    logger.info(
        "[%s] Done: %d bikes across %d path(s), %d invalid",
        config.vendor_name, len(bikes), len(paths), invalid_count,
    )
    return bikes, invalid_count
