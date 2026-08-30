"""Lightspeed eCom (SEOshop) pipeline, via the storefront's own JSON renderer.

Eight Australian shops sat in ``docs/vendors.md`` under "JS-rendered products",
written off because the category page ships an empty product grid and there is
no ``/products.json``. That reading came from testing ``?format=json`` on the
*homepage*, where it returns page metadata and nothing else. On a **category**
URL the same parameter returns the whole listing, fully server-side:

    GET /bikes/?format=json&limit=100

      {"collection": {"count": 192, "pages": 2, "limit": 100,
                      "products": {"61574275": {"title": ..., "sku": ...,
                          "price": {"price_incl": 2999, "price_old_incl": 4499},
                          "available": true, "brand": {"title": "Cannondale"},
                          "variant": "\\"Size: 56\\",\\"Colour: Jet Black\\""}}}}

That is better data than most DOM scrapes: an explicit sale/RRP pair, a stock
flag, the shop's SKU, a real brand field, and a frame size on a declared size
axis rather than parsed out of a colour name.

Three mechanics are easy to get wrong, and none of them fail loudly:

* **Pagination is a path segment, not a query parameter.** Page two is
  ``/bikes/page2.html?format=json&limit=100``. A plain ``&page=2`` returns
  HTTP 200 and re-serves page one, so a shop is silently truncated at 100.
* **``limit`` is not free-form.** ``limit=250`` falls back to the theme default
  of 12, quietly, and again with a 200. 100 is honoured.
* **Categories nest, and a parent renders a grid of subcategories rather than
  products.** The response then carries ``catalog.categories`` instead of
  ``collection``, so the walk has to recurse until it finds a ``collection``.
  Wembley Cycles keeps its bikes three levels down.
"""
import asyncio
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

# The only page size the renderer honours. See the module docstring.
PAGE_SIZE = 100
# How deep to recurse the category tree. Four covers every shop seen
# (Wembley's bikes sit at depth three) without letting a cycle run away.
MAX_DEPTH = 4
# Hard ceiling on categories visited per vendor, so a mis-configured root path
# (e.g. the whole catalogue) can't turn one vendor into thousands of requests.
MAX_CATEGORIES = 60

# Lightspeed serves product images off one CDN, keyed by shop id and image id.
# Any filename works; the path segment is a resize spec, and 500x500x2 is a
# retina 1000px square, which is what the listing cards want.
_IMAGE_URL = "https://cdn.shoplightspeed.com/shops/{shop_id}/files/{image_id}/500x500x2/image.jpg"

# ``variant`` is a flat string of quoted axis pairs, not an object:
#     "Size: 56","Colour: Jet Black"
# Only the size axis is wanted. Colour must never be read as a frame size.
# scrapers/pipelines/shopify.py documents what that costs the size filter.
_SIZE_AXIS_RE = re.compile(r'"?\s*(?:frame\s+)?size\s*:\s*([^",]+)', re.IGNORECASE)


def _is_electric(segment: str) -> bool:
    """True if a category path segment denotes electric bikes.

    Hyphens are dropped so ``e-bikes``, ``ebikes``, ``electric-bikes`` and
    compounds like ``e-bike-mountain`` are all recognised. Mirrors
    :func:`scrapers.pipelines.woocommerce_api._is_electric_slug`; missing a
    spelling here silently files e-MTBs as Mountain.
    """
    flat = segment.replace("-", "").replace("_", "").lower()
    return "electric" in flat or "ebike" in flat


def _category_candidates(path: str, title: str) -> list[str]:
    """Category-matching candidates for a product, best signal first.

    The category *path* the product was walked to is a far better signal than
    its title, so path segments come first, deepest segment first
    (``bikes/mountain/enduro`` asks about "enduro" before "mountain").

    Electric segments jump the queue: a shop that nests ``/e-bikes/mountain/``
    would otherwise resolve every e-MTB as Mountain, because the deepest
    segment wins. Same rule, and the same reason, as the Store API pipeline.
    """
    segments = [s for s in path.split("/") if s]
    ordered = list(reversed(segments))
    # Stable, so the deepest-first order survives within each group.
    ordered.sort(key=lambda s: not _is_electric(s))
    return [s.lower() for s in ordered] + [title.lower()]


def _frame_size(variant: str | None) -> str:
    """Frame size off the declared size axis, or ``"N/A"``."""
    match = _SIZE_AXIS_RE.search(variant or "")
    if not match:
        return "N/A"
    size = match.group(1).strip()
    return extract_frame_size(size) if size else "N/A"


def _price_pair(price: dict) -> tuple[float | None, float | None]:
    """(sale, original) in dollars, or (None, ...) when there is no usable price.

    ``price_old_incl`` is 0 rather than null when a product is not on sale, and
    a few listings carry an "old" price at or below the current one, which is
    not a discount. Both collapse to None so ``compute_discount`` reports 0.
    """
    try:
        sale = float(price.get("price_incl") or 0)
        original = float(price.get("price_old_incl") or 0)
    except (TypeError, ValueError):
        return None, None
    if sale <= 0:
        return None, None
    return sale, (original if original > sale else None)


def _build_record(
    config: VendorConfig,
    product: dict,
    path: str,
    shop_id: int | str | None,
    now: datetime,
) -> BikeRecord | None:
    """One BikeRecord, or None when the product isn't usable or isn't categorised.

    Raises nothing: validation failures are the caller's to count.
    """
    title = (product.get("title") or "").strip()
    url = (product.get("url") or "").strip()
    if not title or not url:
        return None

    sale, original = _price_pair(product.get("price") or {})
    if sale is None:
        logger.debug("[%s] Skipping %r: no usable price", config.vendor_name, title)
        return None

    category = None
    if config.collection_category_map:
        category = config.collection_category_map.get(path)
    if category is None:
        category = resolve_category(_category_candidates(path, title), config.category_map)
    if category is None:
        return None

    brand = (product.get("brand") or {}).get("title") or config.vendor_name
    if config.brand_map:
        brand = config.brand_map.get(brand, brand)

    image_id = product.get("image")
    image_url = (
        _IMAGE_URL.format(shop_id=shop_id, image_id=image_id)
        if image_id and shop_id else None
    )

    frame_size = _frame_size(product.get("variant"))
    product_url = f"{config.base_url}/{url.lstrip('/')}"

    return BikeRecord(
        id=make_bike_id(config.vendor_name, product_url, frame_size, config.city),
        vendor_name=config.vendor_name,
        city=config.city,
        brand=brand,
        model_name=title,
        category=category,
        frame_size=frame_size,
        price_original=original,
        price_sale=sale,
        discount_percentage=compute_discount(sale, original),
        in_stock=bool(product.get("available")),
        product_url=product_url,
        image_url=image_url,
        scraped_at=now,
        last_seen_at=now,
        sku=(product.get("sku") or "").strip() or None,
    )


def _products_of(payload: dict) -> list[dict]:
    """The product rows on a collection payload, whichever shape they arrive in."""
    products = (payload.get("collection") or {}).get("products") or {}
    return list(products.values()) if isinstance(products, dict) else list(products)


async def _fetch(
    config: VendorConfig, client: httpx.AsyncClient, path: str, page: int
) -> dict | None:
    """One category page as JSON, or None if it can't be read.

    Page one is the bare category URL; later pages are ``pageN.html``. See the
    module docstring for why ``&page=N`` is not used.
    """
    segment = "" if page == 1 else f"page{page}.html"
    url = f"{config.base_url}/{path}/{segment}?format=json&limit={PAGE_SIZE}"
    resp = await get_with_retry(client, url, headers={"User-Agent": SCRAPER_USER_AGENT})
    if resp.status_code != 200:
        logger.warning(
            "[%s] %s returned HTTP %d", config.vendor_name, url, resp.status_code
        )
        return None
    try:
        return resp.json()
    except ValueError:
        logger.warning("[%s] %s did not return JSON", config.vendor_name, url)
        return None


async def _walk(
    config: VendorConfig,
    client: httpx.AsyncClient,
    path: str,
    seen_paths: set[str],
    rows: dict[tuple, tuple[dict, str]],
    depth: int = 0,
) -> None:
    """Depth-first walk of one category, collecting product rows as it goes.

    Rows are keyed by (product id, variant id) so that a bike reachable from two
    categories is stored once, while two sizes of the same bike, which
    Lightspeed lists as separate rows, are both kept.
    """
    if depth > MAX_DEPTH or path in seen_paths or len(seen_paths) >= MAX_CATEGORIES:
        return
    seen_paths.add(path)

    payload = await _fetch(config, client, path, page=1)
    if payload is None:
        return

    collection = payload.get("collection")
    if isinstance(collection, dict) and "products" in collection:
        total_pages = collection.get("pages") or 1
        if config.max_pages:
            total_pages = min(total_pages, config.max_pages)
        for page in range(1, int(total_pages) + 1):
            if page > 1:
                await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))
                payload = await _fetch(config, client, path, page=page)
                if payload is None:
                    break
            for product in _products_of(payload):
                rows.setdefault((product.get("id"), product.get("vid")), (product, path))
        return

    # Not a listing: a grid of subcategories. Recurse into the real ones:
    # `type` is "text" for CMS pages (About Us, Workshop) that carry no products.
    children = (payload.get("catalog") or {}).get("categories") or {}
    for child in children.values():
        if child.get("type") != "category" or not child.get("url"):
            continue
        await asyncio.sleep(random.uniform(*SCRAPER_DELAY_RANGE))
        await _walk(config, client, child["url"], seen_paths, rows, depth + 1)


async def scrape_lightspeed(
    config: VendorConfig, client: httpx.AsyncClient
) -> tuple[list[BikeRecord], int]:
    if not config.collections:
        logger.error(
            "[%s] lightspeed pipeline requires `collections` (root category paths)",
            config.vendor_name,
        )
        return [], 0

    if not await check_robots(config.base_url, client):
        logger.warning("[%s] Skipping, disallowed by robots.txt", config.vendor_name)
        return [], 0

    logger.info("[%s] Scraping...", config.vendor_name)
    now = datetime.now(timezone.utc)

    seen_paths: set[str] = set()
    rows: dict[tuple, tuple[dict, str]] = {}
    shop_id: int | str | None = None

    for root in config.collections:
        try:
            await _walk(config, client, root, seen_paths, rows)
        except CloudflareChallenge:
            raise  # not transient: fail the vendor so its existing data is kept
        except Exception as exc:
            logger.error(
                "[%s] Failed walking category %r: %s", config.vendor_name, root, exc
            )

    # The image CDN path needs the numeric shop id, which every payload carries.
    # Read it once from the root category rather than assuming it.
    if rows:
        root_payload = await _fetch(config, client, config.collections[0], page=1)
        shop_id = (root_payload or {}).get("shop", {}).get("id")
        if shop_id is None:
            logger.warning(
                "[%s] No shop id in the payload; images will be omitted",
                config.vendor_name,
            )

    bikes: list[BikeRecord] = []
    invalid_count = 0
    category_skipped = 0
    for product, path in rows.values():
        try:
            record = _build_record(config, product, path, shop_id, now)
        except Exception as exc:
            invalid_count += 1
            logger.warning(
                "[%s] Validation error for %r: %s",
                config.vendor_name, product.get("title"), exc,
            )
            continue
        if record is None:
            category_skipped += 1
            continue
        bikes.append(record)

    if category_skipped and not bikes:
        logger.warning(
            "[%s] produced 0 bikes but skipped %d product(s), check category_map",
            config.vendor_name, category_skipped,
        )

    logger.info(
        "[%s] Done: %d bikes from %d row(s) across %d categor(ies), %d invalid",
        config.vendor_name, len(bikes), len(rows), len(seen_paths), invalid_count,
    )
    return bikes, invalid_count
