"""Choose the one bike to post today.

Reads the public feed rather than the database on purpose: the post then sees
exactly what a visitor sees, so it can never advertise a deal the site does not
show. The database is consulted only for the ledger of what has already been
posted.
"""
import logging
import os
from urllib.parse import urlparse

import httpx

from scrapers.brands import is_known_brand
from scrapers.registry import load_registry

logger = logging.getLogger(__name__)

API_BASE = os.getenv("BIKEGRID_API_BASE", "https://api.bikegrid.com.au").rstrip("/")

# One page is plenty: the feed is already sorted by discount, and anything past
# the first hundred is not going to win selection.
FEED_LIMIT = 100

# A 15%-off bike is not a post. The threshold is about having something worth
# saying, not about filtering bad data (price_sanity already did that upstream).
MIN_DISCOUNT = 20

# Below this the listing is almost always a kids' bike or a clearance frame,
# and "60% off a $180 bike" reads like spam next to the rest of the feed.
MIN_SALE_PRICE = 400.0

# How long a product stays off the roster after being posted.
REPOST_WINDOW_DAYS = 60


def ledger_key(bike: dict) -> str:
    """The identity the repost window is enforced against.

    ``product_key`` where the shop publishes a SKU, so the same bike appearing
    at a second shop still counts as already covered. The 13% of listings with
    no SKU fall back to the bike id, which is narrower than we would like but
    is the only identity those listings have.
    """
    return bike.get("product_key") or f"bike:{bike['id']}"


def opted_out_vendors() -> frozenset[str]:
    """Shops that have asked not to appear, from their own vendor config."""
    return frozenset(
        config.vendor_name for config in load_registry() if not config.instagram
    )


def _is_http_url(url: str | None) -> bool:
    if not url:
        return False
    return urlparse(url).scheme in ("http", "https")


def rejection_reason(bike: dict, blocked_vendors: frozenset[str], posted: set[str]) -> str | None:
    """Why this bike cannot be today's post, or None if it can."""
    if bike["vendor_name"] in blocked_vendors:
        return "vendor opted out"
    if not bike.get("in_stock"):
        return "out of stock"
    if not _is_http_url(bike.get("image_url")):
        # No usable photo means no card. Not worth posting a bike nobody can see.
        return "no usable image"
    if not bike.get("price_original"):
        # Without an RRP there is no "was/now", which is the whole post.
        return "no original price"
    if (bike.get("discount_percentage") or 0) < MIN_DISCOUNT:
        return f"discount below {MIN_DISCOUNT}%"
    if (bike.get("price_sale") or 0) < MIN_SALE_PRICE:
        return f"sale price below {MIN_SALE_PRICE:.0f}"
    if not is_known_brand(bike.get("brand", "")):
        # Filters the unbranded and accessory noise that survives the feed.
        return "unrecognised brand"
    if ledger_key(bike) in posted:
        return f"posted within {REPOST_WINDOW_DAYS} days"
    return None


def select_deal(
    bikes: list[dict], posted: set[str], blocked_vendors: frozenset[str]
) -> dict | None:
    """The best postable bike, or None when nothing qualifies today.

    None is a normal outcome, not an error. An empty day beats a bad post, and
    the caller exits cleanly on it.
    """
    for bike in sorted(bikes, key=lambda b: b.get("discount_percentage") or 0, reverse=True):
        reason = rejection_reason(bike, blocked_vendors, posted)
        if reason is None:
            return bike
        logger.debug("skipped %s (%s): %s", bike.get("id"), bike.get("model_name"), reason)
    return None


async def fetch_deals(client: httpx.AsyncClient) -> list[dict]:
    """Today's discounted, in-stock listings, best discount first."""
    response = await client.get(
        f"{API_BASE}/api/v1/bikes",
        params={
            "added_since": "day",
            "sort": "discount_desc",
            "in_stock": "true",
            "min_discount": MIN_DISCOUNT,
            "limit": FEED_LIMIT,
        },
    )
    response.raise_for_status()
    return response.json()["results"]
