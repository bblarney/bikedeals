import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlencode

import httpx
from bs4 import BeautifulSoup

from scrapers.config import SCRAPER_DELAY_RANGE, SCRAPER_USER_AGENT
from scrapers.models import BikeRecord, VendorConfig, compute_discount, make_bike_id
from scrapers.utils import CloudflareChallenge, check_robots, get_with_retry, parse_price, resolve_category

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"\$([\d,]+(?:\.\d{2})?)\s*$")


def _price_from_aria(aria_label: str) -> float | None:
    """Extract price from BigCommerce aria-label: 'PRODUCT NAME, $16,800.00'."""
    m = _PRICE_RE.search(aria_label.strip())
    return parse_price(m.group(1)) if m else None


async def _scrape_bigcommerce_path(
    config: VendorConfig,
    client: httpx.AsyncClient,
    shop_path: str,
    seen_urls: set[str],
    now: datetime,
) -> tuple[list[BikeRecord], int, int]:
    headers = {"User-Agent": SCRAPER_USER_AGENT}
    bikes: list[BikeRecord] = []
    invalid_count = 0
    path = shop_path.strip("/")
    page = 1

    while True:
        params = {"page": page} if page > 1 else {}
        qs = ("?" + urlencode(params)) if params else ""
        url = f"{config.base_url}/{path}/{qs}"

        try:
            resp = await get_with_retry(client, url, headers=headers)
            resp.raise_for_status()
        except CloudflareChallenge:
            raise  # not transient — abort the vendor so its data is preserved
        except Exception as exc:
            logger.error("[%s] Failed to fetch page %d (%s): %s", config.vendor_name, page, path, exc)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        products = soup.select("li.product")

        if not products:
            break

        for item in products:
            card = item.select_one("article.card")
            if not card:
                continue

            # Title and URL from card-title link
            title_link = card.select_one("h4.card-title > a") or card.select_one("h3.card-title > a")
            if not title_link:
                continue
            model_name = title_link.get_text(strip=True)
            if not model_name:
                continue

            raw_href = title_link.get("href", "")
            product_url = urljoin(config.base_url, raw_href) if raw_href else ""
            if not product_url or product_url in seen_urls:
                continue
            seen_urls.add(product_url)

            # Price lives in the aria-label (static HTML doesn't populate span.price)
            fig_link = card.select_one("a.card-figure__link")
            aria = (fig_link or title_link).get("aria-label", "")
            price_sale = _price_from_aria(aria)
            if price_sale is None or price_sale <= 0:
                logger.debug("[%s] Skipping product with no price: %r", config.vendor_name, model_name)
                continue

            image_url = None
            img = card.select_one("img.card-image")
            if img:
                image_url = img.get("data-src") or img.get("src")
                if image_url and image_url.endswith(".svg"):
                    image_url = None

            # Category: resolve against model name + path (path acts as category hint)
            category = resolve_category([model_name.lower(), path.lower()], config.category_map)
            if category is None:
                logger.debug("[%s] No category match for %r (path=%r); skipping", config.vendor_name, model_name, path)
                continue

            brand = config.vendor_name
            if config.brand_map:
                for key, val in config.brand_map.items():
                    if key.lower() in model_name.lower():
                        brand = val
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

        # BigCommerce pagination: stop if no next-page link
        next_link = soup.select_one("li.pagination-item--next a.pagination-link")
        if not next_link:
            break

        page += 1
        await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))

    return bikes, page, invalid_count


async def scrape_bigcommerce(config: VendorConfig, client: httpx.AsyncClient) -> tuple[list[BikeRecord], int]:
    if not await check_robots(config.base_url, client):
        logger.warning("[%s] Skipping — disallowed by robots.txt", config.vendor_name)
        return [], 0

    logger.info("[%s] Scraping...", config.vendor_name)
    now = datetime.now(timezone.utc)

    paths = config.shop_paths if config.shop_paths else [config.shop_path]
    seen_urls: set[str] = set()
    bikes: list[BikeRecord] = []
    total_pages = 0
    invalid_count = 0

    for path in paths:
        path_bikes, pages, invalid = await _scrape_bigcommerce_path(config, client, path, seen_urls, now)
        bikes.extend(path_bikes)
        total_pages += pages
        invalid_count += invalid
        if len(paths) > 1:
            await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))

    logger.info(
        "[%s] Done: %d bikes across %d path(s), %d page(s), %d invalid",
        config.vendor_name, len(bikes), len(paths), total_pages, invalid_count,
    )
    return bikes, invalid_count
