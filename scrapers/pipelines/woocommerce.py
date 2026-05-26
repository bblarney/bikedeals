import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from scrapers.models import BikeRecord, VendorConfig, compute_discount, make_bike_id

logger = logging.getLogger(__name__)


async def _check_robots(base_url: str, client: httpx.AsyncClient) -> bool:
    try:
        resp = await client.get(f"{base_url}/robots.txt", follow_redirects=True)
        if resp.status_code != 200:
            return True
        text = resp.text.lower()
        in_relevant_agent = False
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                in_relevant_agent = agent in ("*", "bikedeals-scraper")
            elif in_relevant_agent and line.startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path in ("/", "/*"):
                    logger.warning("[%s] robots.txt disallows scraping: %s", base_url, path)
                    return False
        return True
    except Exception as exc:
        logger.warning("[%s] robots.txt check failed (%s); proceeding", base_url, exc)
        return True


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text.strip())
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _resolve_category(
    model_name: str, category_map: dict[str, str]
) -> str | None:
    lower = model_name.lower()
    for key, value in category_map.items():
        if key in lower:
            return value
    return None


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

    if not await _check_robots(config.base_url, client):
        logger.warning("[%s] Skipping — disallowed by robots.txt", config.vendor_name)
        return []

    headers = {"User-Agent": "BikeDeals-Scraper/1.0 (+https://bikedeals.example.com)"}
    sel = config.selectors
    bikes: list[BikeRecord] = []
    now = datetime.now(timezone.utc)
    page = 1

    while True:
        url = f"{config.base_url}/shop/page/{page}/" if page > 1 else f"{config.base_url}/shop/"
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
            raw_original = _sel(item, sel.get("price_original", "")) if sel.get("price_original") else None

            price_sale = _parse_price(raw_sale)
            price_original = _parse_price(raw_original)

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

            brand = config.vendor_name

            category = _resolve_category(model_name, config.category_map)
            if category is None:
                logger.debug(
                    "[%s] No category match for %r; skipping",
                    config.vendor_name, model_name,
                )
                continue

            discount = compute_discount(price_sale, price_original)
            bike_id = make_bike_id(config.vendor_name, product_url, frame_size)

            try:
                record = BikeRecord(
                    id=bike_id,
                    vendor_name=config.vendor_name,
                    city=config.city,
                    brand=brand,
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
        await asyncio.sleep(random.uniform(1.0, 2.0))

    logger.info("[%s] WooCommerce scrape complete: %d bikes", config.vendor_name, len(bikes))
    return bikes
