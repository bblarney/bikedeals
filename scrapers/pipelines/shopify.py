import asyncio
import logging
import random
import re
from datetime import datetime, timezone

import httpx

from scrapers.config import SCRAPER_DELAY_RANGE, SCRAPER_USER_AGENT, SHOPIFY_PAGE_SIZE
from scrapers.models import BikeRecord, VendorConfig, compute_discount, make_bike_id
from scrapers.utils import (
    CloudflareChallenge,
    check_robots,
    extract_frame_size,
    get_with_retry,
    parse_drivetrain_groupset,
    parse_frame_material,
    parse_price,
    resolve_category,
)

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
    # E-bike spares, which shops file inside the e-bike collection itself
    # ("Whiskey Thumb Throttle", $70, listed under /collections/e-bikes).
    "throttle", "charger",
    # A frameset is a frame + fork, not a rideable bike, but shops file it under
    # the discipline collection/product_type of the bike it builds into
    # ("Road Race Bikes"), so only the title distinguishes it. Scooters get the
    # same treatment: shops shelve them in the kids-bike aisle and they have no
    # frame size, but they are not bicycles and don't belong in the feed.
    "frameset", "framesets", "scooter", "scooters",
}

# Canonical brand names — maps any known variant (different casing, store suffix)
# to the single name used in the DB. Add entries here as new variants are found.
_BRAND_ALIASES: dict[str, str] = {
    # Giant variants
    "GIANT": "Giant",
    "Giant Bicycles": "Giant",
    "Giant Brisbane": "Giant",
    "Giant Sydney": "Giant",
    "Giant Gold Coast": "Giant",
    "Giant Sunshine Coast": "Giant",
    "Giant Wollongong": "Giant",
    "Giant Bikes Wollongong": "Giant",
    "Giant Bicycles": "Giant",
    "Giant Australia": "Giant",
    "Giant Melbourne": "Giant",
    "Giant Lygon St": "Giant",
    "Giant South Yarra": "Giant",
    # Full-company vendor strings used by multi-brand stores
    "Specialized Bicycles": "Specialized",
    # Liv variants
    "LIV": "Liv",
    # Other common case variants
    "TREK": "Trek",
    "SPECIALIZED": "Specialized",
    "CANNONDALE": "Cannondale",
    "SCOTT": "Scott",
    "MERIDA": "Merida",
    "CUBE": "Cube",
    "NORCO": "Norco",
    "norco": "Norco",
    "KONA": "Kona",
}


def _normalize_brand(brand: str, brand_map: dict[str, str] | None = None) -> str:
    if brand_map and brand in brand_map:
        return brand_map[brand]
    return _BRAND_ALIASES.get(brand, brand)


_COLOUR_KEYWORDS = {
    "black", "white", "red", "blue", "green", "yellow", "orange", "purple",
    "pink", "grey", "gray", "silver", "gold", "bronze", "brown", "beige",
    "navy", "teal", "cyan", "magenta", "maroon", "olive", "lime", "coral",
}


def _is_accessory(product_type: str) -> bool:
    """Reject on Shopify's own `product_type`, which is category metadata.

    This deliberately no longer looks at the product *title*. Aggressive word
    matching is safe against a category field — a product_type of "Brakes" or
    "Chargers" is unambiguously a part — and unsafe against free text, where
    "Malvern Star Attitude (Disc brake) 24\"" is a real kids' bike and
    "Riese & Muller Charger5" is a real e-bike.

    Titles are now screened by scrapers.product_filter at the orchestrator,
    which applies to all six pipelines rather than this one, and whose terms are
    tuned against the live catalogue to avoid exactly those false positives.
    """
    words = set(
        product_type.lower().replace(":", " ").replace("/", " ").replace("-", " ").split()
    )
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


# "Size", "SIZE", "Frame Size" — the axis that actually carries the frame size.
_FRAME_SIZE_OPTION_RE = re.compile(r"^(?:frame|bike|rider)?\s*size$", re.IGNORECASE)
# Any other axis mentioning size ("SPEC/Size"), excluding the ones that measure
# something that isn't the frame.
_LOOSE_SIZE_OPTION_RE = re.compile(r"\bsize\b", re.IGNORECASE)
_NOT_FRAME_SIZE_RE = re.compile(r"\b(?:wheel|tyre|tire|battery|screen)\b", re.IGNORECASE)


def _size_option_key(product: dict) -> str | None:
    """The variant field ("option1"/"option2"/"option3") holding the frame size.

    Shopify names every variant axis in ``product.options``, so reading the size
    axis directly is the only reliable way to tell a size from a colour. Parsing
    the variant *title* instead cannot: "Forge Grey", "Banksia Orange" and
    "DISRUPT Camo" share no word with any colour vocabulary, so they were being
    recorded as frame sizes and polluting the size filter.

    Returns None when the product exposes no frame-size axis — it is sold in one
    size, or only by colour — which the caller records as "N/A". A "Wheel Size"
    axis is explicitly not a frame size.
    """
    options = product.get("options") or []
    fallback: str | None = None
    for option in options:
        if not isinstance(option, dict):
            continue
        name = str(option.get("name") or "")
        position = option.get("position")
        if not isinstance(position, int) or not 1 <= position <= 3:
            continue
        key = f"option{position}"
        if _FRAME_SIZE_OPTION_RE.match(name.strip()):
            return key
        if (
            fallback is None
            and _LOOSE_SIZE_OPTION_RE.search(name)
            and not _NOT_FRAME_SIZE_RE.search(name)
        ):
            fallback = key
    return fallback


async def _scrape_collection(
    config: VendorConfig,
    client: httpx.AsyncClient,
    collection_handle: str | None,
    seen_handles: set[str],
    now: datetime,
) -> tuple[list[BikeRecord], int, int]:
    """Scrape a single Shopify collection. Returns (bikes, pages_fetched, invalid_count)."""
    headers = {"User-Agent": SCRAPER_USER_AGENT}
    bikes: list[BikeRecord] = []
    invalid_count = 0
    category_skipped = 0

    if collection_handle:
        products_path = f"/collections/{collection_handle}/products.json"
    else:
        products_path = "/products.json"

    next_url: str | None = f"{config.base_url}{products_path}?limit={SHOPIFY_PAGE_SIZE}"
    page = 0

    while next_url:
        page += 1
        logger.debug("[%s] Fetching page %d: %s", config.vendor_name, page, next_url)
        try:
            resp = await get_with_retry(client, next_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except CloudflareChallenge:
            # Not transient and host-wide: abort the whole vendor rather than
            # hammer the remaining collections. Propagates to scrape_vendor,
            # which records it as a failure (so the vendor's data is preserved).
            raise
        except Exception as exc:
            logger.error("[%s] Failed to fetch page %d: %s", config.vendor_name, page, exc)
            break

        products = data.get("products", [])
        logger.debug("[%s] Page %d returned %d products", config.vendor_name, page, len(products))
        if not products:
            break

        # Some collections return a full page yet keep serving products we've
        # already seen (since_id cursoring can loop when products aren't id-ordered).
        # If a page adds nothing new, stop — there's no more data to gather.
        if all(p.get("handle", "") in seen_handles for p in products):
            logger.debug("[%s] Page %d added no new products; stopping", config.vendor_name, page)
            break

        for product in products:
            handle = product.get("handle", "")
            if handle in seen_handles:
                continue
            seen_handles.add(handle)

            brand = _normalize_brand(product.get("vendor", "") or config.vendor_name, config.brand_map)
            model_name = product.get("title", "")
            product_type = product.get("product_type", "") or ""
            tags = product.get("tags", []) or []
            images = product.get("images", [])
            image_url = images[0]["src"] if images else None

            if _is_accessory(product_type):
                continue

            body_html = product.get("body_html") or ""
            frame_material = parse_frame_material(body_html)
            drivetrain_groupset = parse_drivetrain_groupset(body_html)

            raw_updated = product.get("updated_at")
            try:
                product_updated_at = datetime.fromisoformat(raw_updated) if raw_updated else None
            except (ValueError, TypeError):
                product_updated_at = None

            # A curated collection handle is a more reliable category signal than
            # substring-matching generic product_type/tags, so it takes precedence.
            category = None
            if config.collection_category_map and collection_handle in config.collection_category_map:
                category = config.collection_category_map[collection_handle]
            if category is None:
                candidates = [product_type.lower(), model_name.lower()] + [t.lower() for t in tags]
                category = resolve_category(candidates, config.category_map)
            if category is None:
                category_skipped += 1
                logger.debug(
                    "[%s] No category match for %r (type=%r, tags=%r); skipping",
                    config.vendor_name, handle, product_type, tags,
                )
                continue

            # Resolved once per product: every variant shares the same axes.
            size_key = _size_option_key(product)
            has_options = bool(product.get("options"))

            for variant in product.get("variants", []):
                if has_options:
                    # A product with no frame-size axis still gets a record per
                    # variant — colourways can differ in price and stock — but
                    # its size is honestly unknown rather than a colour name.
                    raw_size = variant.get(size_key) if size_key else None
                    frame_size = extract_frame_size(raw_size) if raw_size else "N/A"
                else:
                    # Defensive: every Shopify product observed carries options,
                    # but fall back to the old title parsing if one doesn't.
                    frame_size = extract_frame_size(variant.get("title", ""))
                    if not _is_size_variant(frame_size):
                        continue
                if frame_size.lower().strip() == "default title":
                    frame_size = "N/A"

                variant_id = variant.get("id")
                product_url = f"{config.base_url}/products/{handle}?variant={variant_id}"

                sku = variant.get("sku") or None
                raw_grams = variant.get("grams")
                weight_grams = int(raw_grams) if raw_grams else None

                price_sale = parse_price(variant.get("price"))
                price_original = parse_price(variant.get("compare_at_price"))

                if price_original is not None and price_original <= price_sale:
                    price_original = None

                if price_sale is None or price_sale <= 0:
                    logger.debug("[%s] Skipping variant with invalid price_sale: %s", config.vendor_name, variant)
                    continue

                in_stock = bool(variant.get("available", False))
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
                        sku=sku,
                        weight_grams=weight_grams,
                        product_updated_at=product_updated_at,
                        tags=tags if tags else None,
                        frame_material=frame_material,
                        drivetrain_groupset=drivetrain_groupset,
                    )
                    bikes.append(record)
                except Exception as exc:
                    invalid_count += 1
                    logger.warning(
                        "[%s] Validation error for variant %s/%s: %s",
                        config.vendor_name, handle, frame_size, exc,
                    )

        if len(products) < SHOPIFY_PAGE_SIZE:
            break

        if config.max_pages and page >= config.max_pages:
            logger.warning("[%s] Reached max_pages=%d; stopping early", config.vendor_name, config.max_pages)
            break

        link_header = resp.headers.get("Link", "")
        next_match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        if next_match:
            next_url = next_match.group(1)
        elif collection_handle:
            # /collections/<handle>/products.json does NOT support since_id — it
            # silently ignores the parameter and re-serves page 1, which the
            # "page added no new products" guard above then reads as the end of
            # the collection. Any collection past 250 products was being cut off
            # at 250. It does support ?page=N, so use that.
            next_url = (
                f"{config.base_url}{products_path}"
                f"?limit={SHOPIFY_PAGE_SIZE}&page={page + 1}"
            )
        else:
            since_id = products[-1]["id"]
            next_url = f"{config.base_url}{products_path}?limit={SHOPIFY_PAGE_SIZE}&since_id={since_id}"

        await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))

    # A misconfigured category_map silently yields zero bikes; surface it.
    if category_skipped and not bikes:
        logger.warning(
            "[%s] collection %r produced 0 bikes but skipped %d product(s) with no "
            "category match — check category_map",
            config.vendor_name, collection_handle, category_skipped,
        )

    return bikes, page, invalid_count


async def scrape_shopify(config: VendorConfig, client: httpx.AsyncClient) -> tuple[list[BikeRecord], int]:
    if not await check_robots(config.base_url, client):
        logger.warning("[%s] Skipping — disallowed by robots.txt", config.vendor_name)
        return [], 0

    logger.info("[%s] Scraping...", config.vendor_name)
    now = datetime.now(timezone.utc)

    # Build the list of collection handles to scrape.
    # Multi-collection stores list them in config.collections; single-collection
    # stores use config.collection (which may be None → root /products.json).
    handles: list[str | None] = config.collections if config.collections else [config.collection]

    seen_product_handles: set[str] = set()
    bikes: list[BikeRecord] = []
    total_pages = 0
    invalid_count = 0

    for handle in handles:
        collection_bikes, pages, invalid = await _scrape_collection(
            config, client, handle, seen_product_handles, now
        )
        bikes.extend(collection_bikes)
        total_pages += pages
        invalid_count += invalid
        if len(handles) > 1:
            await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))

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

    logger.info(
        "[%s] Done: %d bikes across %d collection(s), %d page(s), %d invalid",
        config.vendor_name, len(bikes), len(handles), total_pages, invalid_count,
    )
    return bikes, invalid_count
