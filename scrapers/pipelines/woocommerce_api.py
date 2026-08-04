"""WooCommerce Store API pipeline (``/wp-json/wc/store/v1``).

Why this exists alongside :mod:`scrapers.pipelines.woocommerce`: some WooCommerce
shops sit behind a Cloudflare bot challenge that blocks our datacenter egress on
the HTML category pages, and the DOM scrape has no way through. The Store API is
a public, read-only JSON endpoint that WooCommerce Blocks exposes on the same
host, so where it is reachable it is strictly better than parsing listing HTML:

  * per-size rows — ``attributes`` carries the full frame-size term list, where a
    listing card only ever shows one size (the DOM pipeline emits "One Size");
  * exact ``regular_price`` / ``sale_price`` instead of scraped ``<del>``/``<ins>``;
  * a real ``brands`` field, so multi-brand shops don't need slug guesswork.

Products are selected by category, which the API filters by numeric term id, so
the configured category *slugs* are resolved through ``/products/categories``
first. That keeps the vendor YAML readable (slugs are stable and visible in the
shop's URLs; term ids are neither).
"""
import asyncio
import html
import logging
import random
import re
from datetime import datetime, timezone

import httpx

from scrapers.config import SCRAPER_DELAY_RANGE, SCRAPER_USER_AGENT
from scrapers.models import BikeRecord, VendorConfig, compute_discount, make_bike_id
from scrapers.utils import (
    CloudflareChallenge,
    check_robots,
    extract_frame_size,
    get_with_retry,
    resolve_category,
)

logger = logging.getLogger(__name__)

API_PATH = "/wp-json/wc/store/v1"
PAGE_SIZE = 100

# Frame-size terms carry a wheel-size qualifier the size itself doesn't need:
# "Small (F/R 29")", "Extra Small (F 29"/R 27.5")", "Medium - 29". Stripping it
# collapses those to the plain Small/Medium/Large vocabulary the size filter
# uses; without it every wheel size would be its own filter option.
_WHEEL_QUALIFIER_RE = re.compile(r'\s*\([^)]*\)\s*$|\s*-\s*[0-9]+(?:\.[0-9]+)?"?\s*$')


def _clean_text(raw: str | None) -> str:
    """Unescape HTML entities and collapse whitespace.

    Store API strings are HTML-encoded (``Giant Revolt &#8211; Raw Carbon``).
    """
    return " ".join(html.unescape(raw or "").split())


def _price(prices: dict, key: str) -> float | None:
    """Read one price off a Store API ``prices`` object.

    Amounts are integers in the currency's minor unit (``"1399900"`` with
    ``currency_minor_unit: 2`` means $13,999.00), so they must be scaled rather
    than parsed as decimals.
    """
    raw = prices.get(key)
    if raw in (None, ""):
        return None
    try:
        minor = int(prices.get("currency_minor_unit", 2))
        return int(raw) / (10 ** minor)
    except (TypeError, ValueError):
        return None


def _frame_sizes(product: dict) -> list[str]:
    """Frame-size terms for a product, or ``["One Size"]`` if it isn't sized.

    Only the attribute that actually drives variations counts: a decorative
    "Colour" attribute must not be mistaken for a size axis.
    """
    for attr in product.get("attributes") or []:
        name = _clean_text(attr.get("name")).lower()
        if "size" not in name or not attr.get("has_variations"):
            continue
        sizes = []
        for term in attr.get("terms") or []:
            cleaned = _WHEEL_QUALIFIER_RE.sub("", _clean_text(term.get("name")))
            if cleaned:
                sizes.append(extract_frame_size(cleaned))
        if sizes:
            # dict.fromkeys keeps the shop's own size order (XS→XL) while
            # dropping duplicates created by stripping the wheel qualifier.
            return list(dict.fromkeys(sizes))
    return ["One Size"]


def _is_electric_slug(slug: str) -> bool:
    """True if a product-category slug denotes electric bikes.

    Hyphens are dropped before matching so the three spellings shops actually
    use — ``electric-bikes``, ``e-bikes`` and ``ebikes`` (plus compounds like
    ``mtb-ebikes``) — are all recognised. Missing one of them silently breaks
    the electric-first ordering in :func:`_build_records`, which is what keeps
    an e-MTB from being categorised by its mountain category.
    """
    flat = slug.replace("-", "")
    return "electric" in flat or "ebike" in flat


def _known_brands(products: dict[int, dict]) -> list[str]:
    """Brand names this shop uses, longest first."""
    names = {
        _clean_text(b.get("name"))
        for product in products.values()
        for b in (product.get("brands") or [])
    }
    return sorted((n for n in names if n), key=len, reverse=True)


def _resolve_brand(product: dict, known_brands: list[str], config: VendorConfig) -> str:
    """Brand for a product, falling back through name matching to the vendor name."""
    brands = product.get("brands") or []
    brand = _clean_text(brands[0].get("name")) if brands else ""
    if not brand:
        # A few listings have no brand term set at all. Model names carry the
        # brand ("Giant AnyTour X E+ 3 2027"), so match against the brands the
        # shop uses elsewhere rather than mislabelling the bike with the shop's
        # own name — which would otherwise show up as a brand in the filters.
        name = _clean_text(product.get("name"))
        brand = next(
            (b for b in known_brands if re.search(rf"\b{re.escape(b)}\b", name, re.IGNORECASE)),
            "",
        )
    brand = brand or config.vendor_name
    if config.brand_map:
        brand = config.brand_map.get(brand, brand)
    return brand


async def _category_ids(
    config: VendorConfig, client: httpx.AsyncClient, headers: dict
) -> dict[str, int]:
    """Map every product-category slug the shop exposes to its term id."""
    ids: dict[str, int] = {}
    page = 1
    while True:
        url = f"{config.base_url}{API_PATH}/products/categories?per_page={PAGE_SIZE}&page={page}"
        resp = await get_with_retry(client, url, headers=headers)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for cat in batch:
            ids[cat["slug"]] = cat["id"]
        if len(batch) < PAGE_SIZE:
            break
        page += 1
        await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))
    return ids


async def _fetch_category(
    config: VendorConfig, client: httpx.AsyncClient, headers: dict, category_id: int
) -> tuple[list[dict], int]:
    """All products in one category. Returns (products, pages_fetched)."""
    products: list[dict] = []
    page = 1
    while True:
        url = (
            f"{config.base_url}{API_PATH}/products"
            f"?per_page={PAGE_SIZE}&page={page}&category={category_id}"
        )
        resp = await get_with_retry(client, url, headers=headers)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        products.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        if config.max_pages and page >= config.max_pages:
            logger.warning(
                "[%s] Reached max_pages=%d in category %s; stopping early",
                config.vendor_name, config.max_pages, category_id,
            )
            break
        page += 1
        await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))
    return products, page


def _build_records(
    config: VendorConfig, products: dict[int, dict], now: datetime
) -> tuple[list[BikeRecord], int, int]:
    """Turn raw Store API products into BikeRecords.

    Returns (bikes, invalid_count, category_skipped).
    """
    bikes: list[BikeRecord] = []
    invalid_count = 0
    category_skipped = 0
    known_brands = _known_brands(products)

    for product in products.values():
        model_name = _clean_text(product.get("name"))
        permalink = product.get("permalink") or ""
        if not model_name or not permalink:
            continue

        prices = product.get("prices") or {}
        price_sale = _price(prices, "sale_price") or _price(prices, "price")
        price_original = _price(prices, "regular_price")
        if price_sale is None or price_sale <= 0:
            logger.debug("[%s] Skipping %r: no usable price", config.vendor_name, model_name)
            continue
        # Off-sale products report regular == sale; that's "no discount", not a
        # data error (mirrors the Shopify and DOM WooCommerce pipelines).
        if price_original is not None and price_original <= price_sale:
            price_original = None

        slugs = [c.get("slug", "") for c in product.get("categories") or []]
        # Electric slugs first: an e-MTB sits in both the electric and the
        # mountain category, and whichever the API lists first would otherwise
        # decide. Same "e-bike keys before mountain keys" rule the vendor YAMLs
        # already follow for title keywords.
        slugs.sort(key=lambda s: (not _is_electric_slug(s), s))
        category = resolve_category(slugs + [model_name.lower()], config.category_map)
        if category is None:
            category_skipped += 1
            logger.debug(
                "[%s] No category match for %r (slugs=%r); skipping",
                config.vendor_name, model_name, slugs,
            )
            continue

        brand = _resolve_brand(product, known_brands, config)

        images = product.get("images") or []
        image_url = images[0].get("src") if images else None

        # NOTE: stock is product-level. The Store API reports per-variation
        # availability only from /products/<variation_id>, which would be one
        # request per size (hundreds per run), so every size of an in-stock
        # product is recorded in stock. Prices are exact per size: this shop
        # returns price_range: null throughout, meaning one price for all sizes.
        in_stock = bool(product.get("is_in_stock"))
        discount = compute_discount(price_sale, price_original)
        sku = product.get("sku") or None

        for frame_size in _frame_sizes(product):
            bike_id = make_bike_id(config.vendor_name, permalink, frame_size, config.city)
            try:
                bikes.append(BikeRecord(
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
                    product_url=permalink,
                    image_url=image_url,
                    scraped_at=now,
                    last_seen_at=now,
                    sku=sku,
                ))
            except Exception as exc:
                invalid_count += 1
                logger.warning(
                    "[%s] Validation error for %r/%s: %s",
                    config.vendor_name, model_name, frame_size, exc,
                )

    return bikes, invalid_count, category_skipped


async def scrape_woocommerce_api(
    config: VendorConfig, client: httpx.AsyncClient
) -> tuple[list[BikeRecord], int]:
    if not config.collections:
        logger.error(
            "[%s] woocommerce_api pipeline requires `collections` "
            "(product-category slugs)", config.vendor_name,
        )
        return [], 0

    if not await check_robots(config.base_url, client):
        logger.warning("[%s] Skipping — disallowed by robots.txt", config.vendor_name)
        return [], 0

    logger.info("[%s] Scraping...", config.vendor_name)
    now = datetime.now(timezone.utc)
    headers = {"User-Agent": SCRAPER_USER_AGENT}

    try:
        slug_ids = await _category_ids(config, client, headers)
    except CloudflareChallenge:
        raise  # not transient — fail the vendor so its existing data is kept
    except Exception as exc:
        logger.error("[%s] Failed to list product categories: %s", config.vendor_name, exc)
        return [], 0

    # Keyed by product id: configured categories overlap (a bike sits in the
    # umbrella category and its discipline sub-category), so the same product
    # comes back more than once.
    products: dict[int, dict] = {}
    total_pages = 0
    for slug in config.collections:
        category_id = slug_ids.get(slug)
        if category_id is None:
            logger.warning(
                "[%s] Category slug %r not found on the shop; skipping",
                config.vendor_name, slug,
            )
            continue
        try:
            batch, pages = await _fetch_category(config, client, headers, category_id)
        except CloudflareChallenge:
            raise
        except Exception as exc:
            logger.error("[%s] Failed to fetch category %r: %s", config.vendor_name, slug, exc)
            continue
        total_pages += pages
        for product in batch:
            products.setdefault(product["id"], product)
        if len(config.collections) > 1:
            await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))

    bikes, invalid_count, category_skipped = _build_records(config, products, now)

    if category_skipped and not bikes:
        logger.warning(
            "[%s] produced 0 bikes but skipped %d product(s) with no category "
            "match — check category_map", config.vendor_name, category_skipped,
        )

    logger.info(
        "[%s] Done: %d bikes from %d product(s) across %d categor(ies), %d page(s), %d invalid",
        config.vendor_name, len(bikes), len(products), len(config.collections),
        total_pages, invalid_count,
    )
    return bikes, invalid_count
