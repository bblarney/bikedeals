import asyncio
import logging
import random
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from scrapers.config import SCRAPER_DELAY_RANGE, SCRAPER_USER_AGENT
from scrapers.models import BikeRecord, VendorConfig, compute_discount, make_bike_id
from scrapers.utils import CloudflareChallenge, check_robots, get_with_retry, parse_price, resolve_category

logger = logging.getLogger(__name__)

# Map URL path segments to category candidates for resolve_category.
# Used as a fallback when scraping the outlet path (mixed categories).
_URL_CATEGORY_SEGMENTS = ("road-bikes", "mountain-bikes", "gravel-bikes")


async def scrape_canyon(config: VendorConfig, client: httpx.AsyncClient) -> tuple[list[BikeRecord], int]:
    """Scrape Canyon Bicycles AU (canyon.com/en-au).

    Canyon runs Salesforce Commerce Cloud with server-rendered product tiles.
    All category pages support ?start=0&sz=200 to return the full catalogue in
    one request, so there is no pagination loop.  The outlet path mixes
    categories; category is resolved from the product's canonical URL in that
    case.
    """
    if not await check_robots(config.base_url, client):
        logger.warning("[%s] Skipping — disallowed by robots.txt", config.vendor_name)
        return [], 0

    logger.info("[%s] Scraping...", config.vendor_name)
    headers = {"User-Agent": SCRAPER_USER_AGENT}
    now = datetime.now(timezone.utc)

    paths = config.shop_paths or []
    seen_urls: set[str] = set()
    bikes: list[BikeRecord] = []
    invalid_count = 0

    for path in paths:
        url = f"{config.base_url}/{path.strip('/')}/?start=0&sz=200"
        try:
            resp = await get_with_retry(client, url, headers=headers)
            resp.raise_for_status()
        except CloudflareChallenge:
            raise  # not transient — abort the vendor so its data is preserved
        except Exception as exc:
            logger.error("[%s] Failed to fetch %s: %s", config.vendor_name, path, exc)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        tiles = soup.select("li.productGrid__listItem")

        if not tiles:
            logger.debug("[%s] No products found at %s", config.vendor_name, path)
            continue

        # Last path segment used as primary category hint (e.g. "road-bikes").
        path_hint = path.strip("/").split("/")[-1]

        for tile in tiles:
            for script in tile.select("script"):
                script.decompose()

            wrapper = tile.select_one("div.productTileDefault")
            if not wrapper:
                continue

            # Product name — dedicated element; fall back to image-link title attr.
            name_el = wrapper.select_one(".productTileDefault__productName")
            model_name = name_el.get_text(strip=True) if name_el else ""
            if not model_name:
                img_link = wrapper.select_one("a.productTileDefault__imageLink")
                model_name = (img_link.get("title", "") if img_link else "").strip()
            if not model_name:
                continue

            # Product URL — strip query string (colour variant param) for a
            # stable canonical key.
            img_link = wrapper.select_one("a.productTileDefault__imageLink")
            if not img_link:
                continue
            raw_href = img_link.get("href", "")
            product_url = urljoin(config.base_url, raw_href.split("?")[0])
            if not product_url or product_url in seen_urls:
                continue
            seen_urls.add(product_url)

            # Prices — Canyon AU format: "From 12,879 AU$" / "14,049 AU$".
            # parse_price strips all non-numeric chars, so the prefix and
            # trailing " AU$" are handled automatically.
            sale_el = wrapper.select_one(".productTile__priceSale")
            orig_el = wrapper.select_one(".productTile__priceOriginal")
            price_sale = parse_price(sale_el.get_text(strip=True) if sale_el else None)
            price_original = parse_price(orig_el.get_text(strip=True) if orig_el else None)

            if not price_sale or price_sale <= 0:
                logger.debug("[%s] Skipping %r — no price", config.vendor_name, model_name)
                continue

            # Image — Canyon uses standard src (native lazy loading, no data-src).
            img = wrapper.select_one("img.productTileDefault__image")
            image_url = img.get("src") if img else None

            # Category — for non-outlet paths, path_hint is sufficient.
            # For outlet, derive from the product URL which encodes the true
            # category (e.g. /outlet-bikes/road-bikes/... or /road-bikes/...).
            url_hint = next(
                (seg for seg in _URL_CATEGORY_SEGMENTS if seg in product_url), ""
            )
            category = resolve_category(
                [path_hint, url_hint, model_name.lower()],
                config.category_map,
            )
            if category is None:
                logger.debug("[%s] No category for %r; skipping", config.vendor_name, model_name)
                continue

            discount = compute_discount(price_sale, price_original)
            bike_id = make_bike_id(config.vendor_name, product_url, "One Size", config.city)

            try:
                record = BikeRecord(
                    id=bike_id,
                    vendor_name=config.vendor_name,
                    city=config.city,
                    brand="Canyon",
                    model_name=model_name,
                    category=category,
                    frame_size="One Size",
                    price_original=price_original,
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
