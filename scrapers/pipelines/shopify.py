import asyncio
import logging
import random
import re
from datetime import datetime, timezone

import httpx

from scrapers.models import BikeRecord, ScrapeResult, VendorConfig, compute_discount, make_bike_id

logger = logging.getLogger(__name__)

# Product-type words that indicate an accessory, not a bike.
# If any of these words appear in product_type the product is skipped,
# regardless of whether a category key also substring-matches.
_ACCESSORY_WORDS = {
    "helmet", "helmets", "glove", "gloves", "shoe", "shoes", "boot", "boots",
    "jersey", "bib", "sock", "socks", "jacket", "vest", "cap", "shorts",
    "glasses", "goggle", "goggles", "sunglasses", "clothing", "apparel",
    "pump", "lock", "light", "lights", "computer",
    "saddle", "seatpost", "pedal", "pedals",
    "tyre", "tyres", "tire", "tires", "tube", "tubes",
    "grip", "grips", "handlebar", "stem", "fork",
    "cassette", "chain", "brake", "brakes", "derailleur", "crankset",
    "bottle", "cage", "rack", "mudguard", "fender",
    "bag", "backpack", "pannier", "trailer",
    "protection", "accessory", "accessories", "parts",
}

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


def _is_accessory(product_type: str) -> bool:
    words = set(product_type.lower().replace(":", " ").replace("/", " ").replace("-", " ").split())
    return bool(words & _ACCESSORY_WORDS)


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
    product_type: str, tags: list[str], title: str, category_map: dict[str, str]
) -> str | None:
    # Priority order: product_type → title → tags
    # Title is checked before tags because it reliably contains the bike type
    # (e.g. "Trek Marlin 5 Mountain Bike") while tags can be broad/misleading.
    candidates = [product_type.lower(), title.lower()] + [t.lower() for t in tags]
    # Exact key match first
    for candidate in candidates:
        if candidate in category_map:
            return category_map[candidate]
    # Substring match for hierarchical product_type strings and title phrases
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

    logger.info("[%s] Scraping...", config.vendor_name)
    bikes: list[BikeRecord] = []
    now = datetime.now(timezone.utc)

    headers = {"User-Agent": "BikeDeals-Scraper/1.0 (+https://bikedeals.example.com)"}

    if config.collection:
        products_path = f"/collections/{config.collection}/products.json"
    else:
        products_path = "/products.json"

    next_url: str | None = f"{config.base_url}{products_path}?limit=250"
    page = 0

    while next_url:
        page += 1
        logger.debug("[%s] Fetching page %d: %s", config.vendor_name, page, next_url)
        try:
            resp = await client.get(next_url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("[%s] Failed to fetch page %d: %s", config.vendor_name, page, exc)
            break

        products = data.get("products", [])
        logger.debug("[%s] Page %d returned %d products", config.vendor_name, page, len(products))
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

            if _is_accessory(product_type):
                continue

            category = _resolve_category(product_type, tags, model_name, config.category_map)
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

                # compare_at_price must be strictly higher than price to count as a markdown;
                # if it's equal or lower the store has bad data — treat as no sale.
                if price_original is not None and price_original <= price_sale:
                    price_original = None

                if price_sale is None or price_sale <= 0:
                    logger.debug("[%s] Skipping variant with invalid price_sale: %s", config.vendor_name, variant)
                    continue

                in_stock = bool(variant.get("available", False))
                if not in_stock:
                    continue
                discount = compute_discount(price_sale, price_original)
                bike_id = make_bike_id(config.vendor_name, product_url, frame_size, config.city)

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

        if config.max_pages and page >= config.max_pages:
            logger.warning("[%s] Reached max_pages=%d; stopping early", config.vendor_name, config.max_pages)
            break

        # Prefer Shopify cursor (page_info) from Link header — no hard page cap.
        # Fall back to since_id if the store doesn't return a Link header.
        link_header = resp.headers.get("Link", "")
        next_match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        if next_match:
            next_url = next_match.group(1)
            logger.debug("[%s] Following Link cursor to page %d", config.vendor_name, page + 1)
        else:
            since_id = products[-1]["id"]
            next_url = f"{config.base_url}{products_path}?limit=250&since_id={since_id}"
            logger.debug("[%s] No Link header; using since_id=%s", config.vendor_name, since_id)

        await asyncio.sleep(random.uniform(1.0, 2.0))

    # Fan out national chains: duplicate each record once per city
    if config.cities:
        expanded = []
        for bike in bikes:
            for city in config.cities:
                expanded.append(bike.model_copy(update={
                    "city": city,
                    "id": make_bike_id(config.vendor_name, bike.product_url, bike.frame_size, city),
                }))
        bikes = expanded

    logger.info("[%s] Done: %d bikes across %d page(s)", config.vendor_name, len(bikes), page)
    return bikes
