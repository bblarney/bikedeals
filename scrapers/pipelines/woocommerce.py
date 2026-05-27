import asyncio
import logging
import random
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from scrapers.config import SCRAPER_DELAY_RANGE, SCRAPER_USER_AGENT
from scrapers.models import BikeRecord, VendorConfig, compute_discount, make_bike_id
from scrapers.utils import check_robots, parse_price, resolve_category

logger = logging.getLogger(__name__)


def _sel(soup: BeautifulSoup, selector: str) -> str | None:
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else None


def _sel_attr(soup: BeautifulSoup, selector: str, attr: str) -> str | None:
    el = soup.select_one(selector)
    return el.get(attr) if el else None


async def scrape_woocommerce(config: VendorConfig, client: httpx.AsyncClient) -> list[BikeRecord]:
    if not config.selectors:
        logger.error("[%s] WooCommerce pipeline requires selectors config", config.vendor_name)
        return []

    if not await check_robots(config.base_url, client):
        logger.warning("[%s] Skipping — disallowed by robots.txt", config.vendor_name)
        return []

    logger.info("[%s] Scraping...", config.vendor_name)
    headers = {"User-Agent": SCRAPER_USER_AGENT}
    sel = config.selectors
    bikes: list[BikeRecord] = []
    now = datetime.now(timezone.utc)
    page = 1

    while True:
        path = config.shop_path.strip("/")
        url = f"{config.base_url}/{path}/page/{page}/" if page > 1 else f"{config.base_url}/{path}/"
        try:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("[%s] Failed to fetch page %d: %s", config.vendor_name, page, exc)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        products = soup.select(sel["product_list"])

        if not products:
            break

        for item in products:
            model_name = _sel(item, sel["model_name"]) or ""
            if not model_name:
                continue

            raw_sale = _sel(item, sel["price_sale"])
            # Fall back to regular price selector for non-sale items
            if not raw_sale and sel.get("price_regular"):
                raw_sale = _sel(item, sel["price_regular"])
            raw_original = _sel(item, sel.get("price_original", "")) if sel.get("price_original") else None

            price_sale = parse_price(raw_sale)
            price_original = parse_price(raw_original)

            if price_sale is None or price_sale <= 0:
                logger.debug("[%s] Skipping product with invalid price: %r", config.vendor_name, model_name)
                continue

            raw_url = _sel_attr(item, sel["product_url"], "href") or ""
            product_url = urljoin(config.base_url, raw_url) if raw_url else ""
            if not product_url:
                continue

            image_url = _sel_attr(item, sel["image_url"], "src") or _sel_attr(item, sel["image_url"], "data-src")

            frame_size = _sel(item, sel["frame_size"]) if sel.get("frame_size") else "One Size"
            if not frame_size:
                frame_size = "One Size"

            category = resolve_category([model_name.lower()], config.category_map)
            if category is None:
                logger.debug(
                    "[%s] No category match for %r; skipping",
                    config.vendor_name, model_name,
                )
                continue

            discount = compute_discount(price_sale, price_original)
            bike_id = make_bike_id(config.vendor_name, product_url, frame_size, config.city)

            try:
                record = BikeRecord(
                    id=bike_id,
                    vendor_name=config.vendor_name,
                    city=config.city,
                    brand=config.vendor_name,
                    model_name=model_name,
                    category=category,
                    frame_size=frame_size,
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
                logger.warning(
                    "[%s] Validation error for %r: %s",
                    config.vendor_name, model_name, exc,
                )

        # WooCommerce pagination: stop if fewer products than expected or no next page
        next_page = soup.select_one("a.next.page-numbers")
        if not next_page:
            break

        page += 1
        await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))

    logger.info("[%s] Done: %d bikes across %d page(s)", config.vendor_name, len(bikes), page)
    return bikes
