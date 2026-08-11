"""Headless Next.js storefront over an Ecwid (Lightspeed eCom) catalogue.

Shops on this stack render nothing server-side: the category pages and the
product grid are built in the browser, so there is no listing HTML for the
`woocommerce`-style DOM pipeline to key off, and no `/products.json` for the
Shopify one. What *is* served is the catalogue itself — Next.js bakes the
Ecwid product list into one of the page's build chunks as a
``JSON.parse('[…]')`` literal, and the client component renders from it.

That literal is this pipeline's source. One product entry looks like:

    {"id": 809053587, "sku": "17640 - Base", "name": "Norco Fluid A3",
     "price": 2999, "compareToPrice": null, "inStock": true, "enabled": true,
     "brand": "Norco", "imageUrl": "https://…/5786269869.jpg",
     "suggestedCategory": "Bikes / Mountain Bikes / Dual Suspension",
     "categoryPaths": ["Bikes", "Bikes / Mountain Bikes", …]}

which carries everything the normalised schema needs except the public product
URL: the entry's own ``url`` points at the shop's staging host and the legacy
Ecwid ``/store#!/…/p/<id>`` route, neither of which is where a customer lands.
The live URLs are in ``/sitemap.xml``, so products are matched to it by slug
and anything unmatched is dropped rather than recorded with a URL that 404s.

Two limitations, both inherited from what the chunk publishes:

  * **No per-size rows.** The catalogue entry has one price and one stock flag
    for the whole product; sizes live on the product page. Every bike is
    recorded as "One Size", which is what this vendor's previous (WooCommerce
    DOM) config produced too.
  * **No SKU.** ``sku`` is the shop's own POS id ("17640"), not a manufacturer
    part number, so recording it would let two unrelated shops' internal ids
    collide in the cross-shop SKU match. It is deliberately left unset.

The chunk's filename is content-hashed and changes on every deploy, so the
chunks referenced by the listing page are scanned for the catalogue marker
instead of being configured. If a redesign moves the catalogue out of the
bundle the scan finds nothing, the vendor reports zero bikes, and the run keeps
yesterday's rows — the same failure mode as a broken CSS selector.
"""
import ast
import asyncio
import json
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
    get_with_retry,
    resolve_category,
)

logger = logging.getLogger(__name__)

# Field only the catalogue array carries, so it identifies both the right chunk
# and the right literal within it.
CATALOGUE_MARKER = '"categoryPaths"'

_CHUNK_RE = re.compile(r"/_next/static/chunks/[A-Za-z0-9._-]+\.js")
_JSON_PARSE_RE = re.compile(r"JSON\.parse\((['\"])")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


def _slugify(name: str) -> str:
    """Slug for a product name, matching the storefront's own URL slugs."""
    return _SLUG_RE.sub("-", name.lower()).strip("-")


def _end_of_js_string(js: str, start: int) -> int:
    """Index of the quote closing the JS string literal that opens at ``start``."""
    quote = js[start]
    i = start + 1
    while i < len(js):
        if js[i] == "\\":
            i += 2
            continue
        if js[i] == quote:
            return i
        i += 1
    return -1


def _catalogue_from_js(js: str) -> list[dict]:
    """The product array embedded in one build chunk, or ``[]`` if it isn't there.

    The array reaches the browser as JSON *inside a JS string literal*
    (``JSON.parse('[{…}]')``), so it has two layers of escaping: the literal is
    decoded with ``ast.literal_eval`` — which reads Python/JS string escapes
    without evaluating anything — and the result is then parsed as JSON.
    """
    for match in _JSON_PARSE_RE.finditer(js):
        start = match.end() - 1
        end = _end_of_js_string(js, start)
        if end == -1:
            continue
        literal = js[start:end + 1]
        if CATALOGUE_MARKER not in literal:
            continue
        try:
            products = json.loads(ast.literal_eval(literal))
        except (ValueError, SyntaxError) as exc:
            logger.debug("Catalogue literal did not parse: %s", exc)
            continue
        if isinstance(products, list):
            return [p for p in products if isinstance(p, dict)]
    return []


def _is_electric(text: str) -> bool:
    """True if a category path denotes electric bikes.

    Separators are dropped first so ``E Bikes``, ``e-bikes`` and ``ebikes`` all
    match — the same rule the Store API pipeline applies to category slugs, and
    for the same reason: it decides an e-MTB's category before its "Mountain
    Bikes" ancestor can.
    """
    flat = re.sub(r"[\s\-_]", "", text.lower())
    return "electric" in flat or "ebike" in flat


def _category_candidates(product: dict) -> list[str]:
    """Category strings to offer ``resolve_category``, best first.

    Deepest path first (``Bikes / E Bikes / E MTB Bikes`` says more than
    ``Bikes``), electric paths ahead of everything else, product name last.
    """
    paths = [p for p in (product.get("categoryPaths") or []) if isinstance(p, str)]
    suggested = product.get("suggestedCategory") or ""
    candidates = [suggested] + sorted(paths, key=len, reverse=True)
    candidates = [c.lower() for c in candidates if c]
    candidates.sort(key=lambda c: not _is_electric(c))  # stable: electric first
    name = product.get("name") or ""
    return candidates + [name.lower()]


def _in_scope(product: dict, collections: list[str] | None) -> bool:
    """True if the product sits under one of the configured top-level categories.

    The catalogue is the shop's whole Ecwid inventory — helmets, workshop
    services, spare parts — so bikes are selected by their root category path
    rather than by hoping no accessory happens to match ``category_map``.
    """
    if not collections:
        return True
    roots = {(p.split("/")[0].strip()) for p in (product.get("categoryPaths") or [])}
    return bool(roots & set(collections))


def _known_brands(products: list[dict], config: VendorConfig) -> list[str]:
    """Brand names to look for in a product name, longest first.

    The shop's own ``brand`` values, plus the ``brand_map`` keys — a brand that
    appears *only* on products that leave ``brand`` null (a single balance-bike
    label, say) is invisible to the catalogue scan, so the YAML can name it.
    """
    names = {str(p.get("brand") or "").strip() for p in products}
    names |= set(config.brand_map or {})
    return sorted((n for n in names if n), key=len, reverse=True)


def _resolve_brand(product: dict, known_brands: list[str], config: VendorConfig) -> str:
    """Brand for a product, falling back through name matching to the shop name."""
    brand = str(product.get("brand") or "").strip()
    if not brand:
        # Roughly a third of entries leave `brand` null, but the model name
        # always leads with it ("Trek Marlin 7 2027"), so match against the
        # brands the shop sets elsewhere. Labelling the bike with the shop's own
        # name instead would put "Cranks" in the brand filter.
        name = str(product.get("name") or "")
        brand = next(
            (b for b in known_brands if re.search(rf"\b{re.escape(b)}\b", name, re.IGNORECASE)),
            "",
        )
    brand = brand or config.vendor_name
    if config.brand_map:
        brand = config.brand_map.get(brand, config.brand_map.get(brand.lower(), brand))
    return brand


def _price(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


async def _fetch_catalogue(
    config: VendorConfig, client: httpx.AsyncClient, headers: dict
) -> tuple[list[dict], int]:
    """Find and parse the catalogue chunk. Returns (products, requests_made)."""
    listing_url = f"{config.base_url}/{config.shop_path.strip('/')}"
    resp = await get_with_retry(client, listing_url, headers=headers)
    resp.raise_for_status()

    # dict.fromkeys keeps the page's own order: the page-specific chunks are
    # emitted last, and the catalogue is in one of those.
    chunk_paths = list(dict.fromkeys(_CHUNK_RE.findall(resp.text)))
    if not chunk_paths:
        logger.error(
            "[%s] No build chunks referenced by %s — the storefront is not the "
            "expected Next.js app", config.vendor_name, listing_url,
        )
        return [], 1

    requests_made = 1
    for path in reversed(chunk_paths):
        await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))
        try:
            chunk = await get_with_retry(client, f"{config.base_url}{path}", headers=headers)
            requests_made += 1
            chunk.raise_for_status()
        except CloudflareChallenge:
            raise
        except Exception as exc:
            # One unreadable chunk shouldn't sink the vendor — the catalogue is
            # in exactly one of them, and we haven't found it yet.
            logger.warning("[%s] Failed to fetch %s: %s", config.vendor_name, path, exc)
            continue
        if CATALOGUE_MARKER not in chunk.text:
            continue
        products = _catalogue_from_js(chunk.text)
        if products:
            logger.debug(
                "[%s] Catalogue found in %s (%d products)",
                config.vendor_name, path, len(products),
            )
            return products, requests_made

    logger.error(
        "[%s] No catalogue found in %d build chunk(s) — the storefront no longer "
        "ships its product list in the bundle", config.vendor_name, len(chunk_paths),
    )
    return [], requests_made


async def _product_slugs(
    config: VendorConfig, client: httpx.AsyncClient, headers: dict
) -> set[str]:
    """Slugs of every product URL in the sitemap."""
    resp = await get_with_retry(client, f"{config.base_url}/sitemap.xml", headers=headers)
    resp.raise_for_status()
    return {
        url.rstrip("/").rsplit("/", 1)[-1]
        for url in _LOC_RE.findall(resp.text)
        if "/product/" in url
    }


def _build_records(
    config: VendorConfig, products: list[dict], slugs: set[str], now: datetime
) -> tuple[list[BikeRecord], int, int, int]:
    """Turn catalogue entries into BikeRecords.

    Returns (bikes, invalid_count, category_skipped, url_skipped).
    """
    bikes: list[BikeRecord] = []
    invalid_count = 0
    category_skipped = 0
    url_skipped = 0
    known_brands = _known_brands(products, config)

    for product in products:
        # `enabled` is the shop's own published flag: the catalogue also carries
        # discontinued and draft products, which are not for sale.
        if not product.get("enabled") or not _in_scope(product, config.collections):
            continue

        model_name = str(product.get("name") or "").strip()
        if not model_name:
            continue

        price_sale = _price(product.get("price"))
        if price_sale is None or price_sale <= 0:
            logger.debug("[%s] Skipping %r: no usable price", config.vendor_name, model_name)
            continue
        price_original = _price(product.get("compareToPrice"))
        if price_original is not None and price_original <= price_sale:
            price_original = None

        category = resolve_category(_category_candidates(product), config.category_map)
        if category is None:
            category_skipped += 1
            logger.debug(
                "[%s] No category match for %r (paths=%r); skipping",
                config.vendor_name, model_name, product.get("categoryPaths"),
            )
            continue

        slug = _slugify(model_name)
        if slug not in slugs:
            url_skipped += 1
            logger.debug(
                "[%s] %r has no page in the sitemap (slug %r); skipping",
                config.vendor_name, model_name, slug,
            )
            continue

        product_url = f"{config.base_url}/product/{slug}"
        frame_size = "One Size"
        try:
            bikes.append(BikeRecord(
                id=make_bike_id(config.vendor_name, product_url, frame_size, config.city),
                vendor_name=config.vendor_name,
                city=config.city,
                brand=_resolve_brand(product, known_brands, config),
                model_name=model_name,
                category=category,
                frame_size=frame_size,
                price_original=price_original,
                price_sale=price_sale,
                discount_percentage=compute_discount(price_sale, price_original),
                in_stock=bool(product.get("inStock")),
                product_url=product_url,
                image_url=product.get("imageUrl") or product.get("thumbnailUrl") or None,
                scraped_at=now,
                last_seen_at=now,
            ))
        except Exception as exc:
            invalid_count += 1
            logger.warning(
                "[%s] Validation error for %r: %s", config.vendor_name, model_name, exc,
            )

    return bikes, invalid_count, category_skipped, url_skipped


async def scrape_ecwid_next(
    config: VendorConfig, client: httpx.AsyncClient
) -> tuple[list[BikeRecord], int]:
    if not await check_robots(config.base_url, client):
        logger.warning("[%s] Skipping — disallowed by robots.txt", config.vendor_name)
        return [], 0

    logger.info("[%s] Scraping...", config.vendor_name)
    now = datetime.now(timezone.utc)
    headers = {"User-Agent": SCRAPER_USER_AGENT}

    try:
        products, requests_made = await _fetch_catalogue(config, client, headers)
    except CloudflareChallenge:
        raise  # not transient — fail the vendor so its existing data is kept
    except Exception as exc:
        logger.error("[%s] Failed to fetch the catalogue: %s", config.vendor_name, exc)
        return [], 0

    if not products:
        return [], 0

    try:
        await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))
        slugs = await _product_slugs(config, client, headers)
        requests_made += 1
    except CloudflareChallenge:
        raise
    except Exception as exc:
        logger.error("[%s] Failed to fetch the sitemap: %s", config.vendor_name, exc)
        return [], 0

    bikes, invalid_count, category_skipped, url_skipped = _build_records(
        config, products, slugs, now
    )

    if category_skipped and not bikes:
        logger.warning(
            "[%s] produced 0 bikes but skipped %d product(s) with no category "
            "match — check category_map", config.vendor_name, category_skipped,
        )
    if url_skipped:
        logger.warning(
            "[%s] %d product(s) had no matching page in the sitemap — check "
            "whether the storefront changed its product URLs",
            config.vendor_name, url_skipped,
        )

    logger.info(
        "[%s] Done: %d bikes from a %d-product catalogue, %d request(s), %d invalid",
        config.vendor_name, len(bikes), len(products), requests_made, invalid_count,
    )
    return bikes, invalid_count
