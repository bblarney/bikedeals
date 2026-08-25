import hashlib
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from scrapers.utils import canonical_frame_size


def make_bike_id(vendor_name: str, product_url: str, frame_size: str, city: str | None = None) -> str:
    key = f"{vendor_name}::{city or ''}::{product_url}::{frame_size}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Corporate suffixes shops append to the same manufacturer: "Progear" and
# "Progear Bikes", "Specialized" and "Specialized Bicycles". Stripping them
# recovers 38 cross-shop matches that brand-agreement would otherwise reject.
#
# Longest first — "bicycles" must be tried before "cycles", or "specializedbi"
# survives. Substring matching is deliberately NOT used instead: "Liv" is a real
# brand and "Live Life Cycling" is a shop, and one contains the other. Stripping
# a known suffix keeps those apart ("livelife" != "liv") where `in` would not.
_BRAND_SUFFIXES = (
    "bicycles", "bikeco", "bicycle", "cycling", "cycles", "bikes", "cycle", "bike", "bmx",
)
# Never strip down to a stub: a brand genuinely named e.g. "Cycles" must survive.
_MIN_BRAND_STEM = 3


def _canonical_brand(brand: str) -> str:
    stem = _NON_ALNUM.sub("", brand.lower())
    for suffix in _BRAND_SUFFIXES:
        if stem.endswith(suffix) and len(stem) - len(suffix) >= _MIN_BRAND_STEM:
            return stem[: -len(suffix)]
    return stem


def make_product_key(brand: str, sku: str | None) -> str | None:
    """Cross-shop product identity: a SKU only means "same product" if the brand agrees.

    A shop SKU is not globally unique. Several Australian shops run the same
    Lightspeed/Retail POS, and its auto-increment counters collide across
    unrelated stores: SKU ``210000015200`` is a $1,299 Jamis Renegade at
    Melbourne Bicycles and a $9,999 AMFLOW PX Carbon at Summit Cycles. Matching
    on the SKU alone presented those as one product and quoted the Jamis price
    as the AMFLOW's "lowest price" — on the page *and* in its AggregateOffer
    JSON-LD.

    Requiring the brand to agree removes the collisions without costing genuine
    matches. Measured against the live feed (38,724 in-stock listings): of the
    2,185 SKU groups spanning two or more vendors, brand disagreement flags 263,
    and every one inspected was a genuine collision. Gating on price spread was
    tried and rejected — it suppresses exactly the real price differences the
    site exists to surface.

    Returns None when the shop publishes no SKU (13% of listings), which leaves
    the bike unmatched rather than guessing.
    """
    if not sku or not sku.strip():
        return None
    return f"{_canonical_brand(brand)}:{sku.strip()}"


def compute_discount(price_sale: float, price_original: float | None) -> int:
    if not price_original or price_original <= 0:
        return 0
    if price_sale >= price_original:
        return 0
    return round((1 - price_sale / price_original) * 100)


class VendorConfig(BaseModel):
    vendor_name: str
    city: str | None = None      # single-location vendors
    cities: list[str] | None = None  # national chains: one record per city
    base_url: str
    pipeline: Literal[
        "shopify", "woocommerce", "woocommerce_api", "bigcommerce", "giant", "canyon", "custom"
    ]
    category_map: dict[str, str]
    selectors: dict[str, str] | None = None
    collection: str | None = None
    # Curated product groupings to scrape: Shopify collection handles, or
    # WooCommerce product-category slugs for the woocommerce_api pipeline.
    collections: list[str] | None = None
    # Maps a Shopify collection handle -> our category. For collection-targeted
    # stores whose product_type/tags are too generic to categorise (e.g. every
    # product is product_type "Bikes"), the curated collection a product was
    # found in decides its category. Takes precedence over category_map.
    collection_category_map: dict[str, str] | None = None
    max_pages: int | None = None
    shop_path: str = "shop"
    shop_paths: list[str] | None = None    # multi-path WooCommerce/BigCommerce/Giant stores
    brand_map: dict[str, str] | None = None  # vendor-specific brand name overrides


class BikeRecord(BaseModel):
    id: str
    vendor_name: str
    city: str | None
    brand: str
    model_name: str
    category: Literal["Road", "Mountain", "Gravel", "E-Bike", "Commuter"]
    # As the shop published it. Keep it: make_bike_id hashes this, so it is what
    # holds every detail URL and every price_events row in place.
    frame_size: str
    # Derived from frame_size, never set by a pipeline. See canonical_frame_size.
    frame_size_canonical: str | None = None
    price_original: float | None
    price_sale: float
    discount_percentage: int
    in_stock: bool
    product_url: str
    image_url: str | None
    scraped_at: datetime
    last_seen_at: datetime
    sku: str | None = None
    weight_grams: int | None = None
    product_updated_at: datetime | None = None
    tags: list[str] | None = None
    frame_material: str | None = None
    drivetrain_groupset: str | None = None
    # Derived from brand + sku, never set by a pipeline. See make_product_key.
    product_key: str | None = None

    @model_validator(mode="after")
    def derive_frame_size_canonical(self) -> "BikeRecord":
        # Always recomputed for the same reason product_key is: a pipeline that
        # hand-set this would put a size in the filter that no shop published.
        self.frame_size_canonical = canonical_frame_size(self.frame_size)
        return self

    @model_validator(mode="after")
    def derive_product_key(self) -> "BikeRecord":
        # Always recomputed, so a pipeline cannot supply a stale or hand-rolled
        # key and quietly break cross-shop matching.
        self.product_key = make_product_key(self.brand, self.sku)
        return self

    @model_validator(mode="after")
    def check_prices(self) -> "BikeRecord":
        if self.price_original is not None and self.price_sale > self.price_original:
            raise ValueError(
                f"price_sale ({self.price_sale}) > price_original ({self.price_original})"
            )
        return self


class ScrapeResult(BaseModel):
    vendor_name: str
    bikes: list[BikeRecord]
    invalid_count: int = 0
    error: str | None = None
