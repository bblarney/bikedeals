import asyncio
import logging
import random
from datetime import datetime, timezone

import httpx

from scrapers.models import BikeRecord, ScrapeResult, VendorConfig, compute_discount, make_bike_id

logger = logging.getLogger(__name__)

_COLOUR_KEYWORDS = {
    "black", "white", "red", "blue", "green", "yellow", "orange", "purple",
    "pink", "grey", "gray", "silver", "gold", "bronze", "brown", "beige",
    "navy", "teal", "cyan", "magenta", "maroon", "olive", "lime", "coral",
}

_SIZE_KEYWORDS = {
    "xs", "s", "m", "l", "xl", "xxl", "2xl", "3xl",
    "extra small", "small", "medium", "large", "extra large",
    "one size", "one-size", "default",
}


def _is_size_variant(title: str) -> bool:
    lower = title.lower().strip()
    if lower == "default title":
        return False
    # If every word is a colour keyword, it's a colour variant
    words = set(lower.replace("/", " ").split())
    if words and words.issubset(_COLOUR_KEYWORDS):
        return False
    return True


async def _check_robots(base_url: str, client: httpx.AsyncClient) -> bool:
    try:
        resp = await client.get(f"{base_url}/robots.txt", follow_redirects=True)
        if resp.status_code != 200:
            return True  # no robots.txt → assume allowed
        text = resp.text.lower()
        # Look for disallow rules targeting /products.json or /*
        in_relevant_agent = False
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                in_relevant_agent = agent in ("*", "bikedeals-scraper")
            elif in_relevant_agent and line.startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path in ("/", "/*", "/products.json", "/products"):
                    logger.warning("[%s] robots.txt disallows scraping: %s", base_url, path)
                    return False
        return True
    except Exception as exc:
        logger.warning("[%s] robots.txt check failed (%s); proceeding", base_url, exc)
        return True


def _resolve_category(
    product_type: str, tags: list[str], category_map: dict[str, str]
) -> str | None:
    candidates = [product_type.lower()] + [t.lower() for t in tags]
    # Exact key match first (tags are usually short and exact)
    for candidate in candidates:
        if candidate in category_map:
            return category_map[candidate]
    # Substring match: check whether any map key appears inside the candidate.
    # This handles hierarchical product_type strings like
    # "Bikes & Scooters : Bikes : Mountain Bikes" where the key is "mountain bikes".
    for candidate in candidates:
        for key, value in category_map.items():
            if key in candidate:
                return value
    return None


def _parse_price(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


async def scrape_shopify(config: VendorConfig, client: httpx.AsyncClient) -> list[BikeRecord]:
    if not await _check_robots(config.base_url, client):
        logger.warning("[%s] Skipping — disallowed by robots.txt", config.vendor_name)
        return []

    bikes: list[BikeRecord] = []
    page = 1
    now = datetime.now(timezone.utc)

    headers = {"User-Agent": "BikeDeals-Scraper/1.0 (+https://bikedeals.example.com)"}

    while True:
        url = f"{config.base_url}/products.json?limit=250&page={page}"
        try:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            if resp.status_code == 400 and page > 1:
                # Shopify page-based API is hard-capped at page 100
                logger.debug("[%s] Reached Shopify page limit at page %d", config.vendor_name, page)
                break
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("[%s] Failed to fetch page %d: %s", config.vendor_name, page, exc)
            break

        products = data.get("products", [])
        if not products:
            break

        for product in products:
            brand = product.get("vendor", "") or config.vendor_name
            model_name = product.get("title", "")
            product_type = product.get("product_type", "") or ""
            tags = product.get("tags", []) or []
            handle = product.get("handle", "")
            images = product.get("images", [])
            image_url = images[0]["src"] if images else None

            category = _resolve_category(product_type, tags, config.category_map)
            if category is None:
                logger.debug(
                    "[%s] No category match for %r (type=%r, tags=%r); skipping",
                    config.vendor_name, handle, product_type, tags,
                )
                continue

            for variant in product.get("variants", []):
                frame_size = variant.get("title", "")
                if not _is_size_variant(frame_size):
                    continue

                variant_id = variant.get("id")
                product_url = f"{config.base_url}/products/{handle}?variant={variant_id}"

                price_sale = _parse_price(variant.get("price"))
                price_original = _parse_price(variant.get("compare_at_price"))

                if price_sale is None or price_sale <= 0:
                    logger.debug("[%s] Skipping variant with invalid price_sale: %s", config.vendor_name, variant)
                    continue

                in_stock = bool(variant.get("available", False))
                if not in_stock:
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
                        in_stock=in_stock,
                        product_url=product_url,
                        image_url=image_url,
                        scraped_at=now,
                        last_seen_at=now,
                    )
                    bikes.append(record)
                except Exception as exc:
                    logger.warning(
                        "[%s] Validation error for variant %s/%s: %s",
                        config.vendor_name, handle, frame_size, exc,
                    )

        if len(products) < 250:
            break

        page += 1
        await asyncio.sleep(random.uniform(1.0, 2.0))

    logger.info("[%s] Shopify scrape complete: %d bikes", config.vendor_name, len(bikes))
    return bikes
