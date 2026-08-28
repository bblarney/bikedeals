"""Ask Shopify's image CDN for a card-sized copy of a product photo.

A direct port of ``shopImage`` in frontend/src/lib/images.js, and deliberately
the same fifteen lines rather than anything cleverer: the frontend and the post
card should ask the CDN for images the same way, and the reason for the
single-host scoping is unchanged. 98% of our product images are on
cdn.shopify.com and none of the scraped URLs carry a size, so without this the
renderer pulls a 2-3 MB original to paint a 1000px slot. The other ~2% sit on
assorted vendor CDNs with no shared transform contract and pass through
untouched.
"""
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

SHOPIFY_CDN_HOST = "cdn.shopify.com"


def shop_image(url: str | None, width: int) -> str | None:
    if not url:
        return url
    try:
        parts = urlparse(url)
        if parts.hostname != SHOPIFY_CDN_HOST:
            return url
        # Overwrite any width already present rather than appending a second
        # one, and preserve Shopify's ?v= cache key.
        query = [(k, v) for k, v in parse_qsl(parts.query) if k != "width"]
        query.append(("width", str(width)))
        return urlunparse(parts._replace(query=urlencode(query)))
    except ValueError:
        return url
