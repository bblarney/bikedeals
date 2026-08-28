from datetime import datetime

from pydantic import BaseModel, EmailStr


class BikeResponse(BaseModel):
    id: str
    vendor_name: str
    city: str | None
    brand: str
    model_name: str
    category: str
    # frame_size is the shop's own wording; frame_size_canonical is that size on
    # a shared scale, or null when the shop published nothing usable. Clients
    # should show the canonical one and fall back to the raw.
    frame_size: str
    frame_size_canonical: str | None = None
    price_original: float | None
    price_sale: float
    discount_percentage: int
    in_stock: bool
    product_url: str
    image_url: str | None
    scraped_at: datetime
    last_seen_at: datetime
    click_count: int
    price_drop_at: datetime | None = None
    discount_started_at: datetime | None = None
    frame_material: str | None = None
    drivetrain_groupset: str | None = None
    sku: str | None = None
    # Cross-shop identity. Pass back as ?product_key= to list every shop selling
    # this exact product; sku alone is not safe for that (brand collisions).
    product_key: str | None = None
    # Distinct *vendors* carrying this product, not storefronts — 0 when there
    # is no cross-shop match to show.
    sku_vendor_count: int = 0
    # Cheapest in-stock price for this product at any shop, over the same rows
    # sku_vendor_count counts, so it can equal this listing's own price when
    # this listing is the cheapest. Null when there is no cross-shop match.
    # Like the count, it spans the whole catalogue and ignores the request's
    # filters: it answers "what does this cost elsewhere", not "within my
    # current view". Feed-only; the detail response carries `lowest_price`,
    # which is the same number computed from the offers it already returns.
    sku_min_price: float | None = None
    # How many of *this* vendor's storefronts carry the listing. A chain lists
    # one national catalogue per city, so those rows collapse to a single result
    # and this is what lets the card still say "at 8 stores". Always 1 once the
    # feed is filtered to a city.
    location_count: int = 1
    # Every size this vendor stocks of the product, smallest first. The feed
    # returns one row per product rather than one per size, and this is what the
    # card shows in place of the sizes it collapsed; the row's own frame_size is
    # one of them. Narrows with ?size=, exactly as location_count narrows with
    # ?city=. Empty when the shop published no usable size ("One Size", "N/A").
    #
    # Feed-only: the detail response carries `variants` instead, which is richer
    # (a bike id and a price per size) and spans every shop, not just this one.
    sizes: list[str] = []

    model_config = {"from_attributes": True}


class PaginatedBikes(BaseModel):
    total: int
    limit: int
    offset: int
    results: list[BikeResponse]


class OfferResponse(BaseModel):
    bike_id: str
    vendor_name: str
    city: str | None
    frame_size: str
    price_original: float | None
    price_sale: float
    discount_percentage: int
    in_stock: bool
    product_url: str
    last_seen_at: datetime
    # How many of this vendor's storefronts carry the product. Chains list one
    # national catalogue at one price, so they collapse to a single offer row
    # rather than one per city; this is what lets the UI still say "also at 7
    # other stores". `city` is the city of the cheapest listing.
    location_count: int = 1

    model_config = {"from_attributes": True}


class VariantResponse(BaseModel):
    bike_id: str
    frame_size: str
    price_sale: float
    in_stock: bool

    model_config = {"from_attributes": True}


class BikeDetailResponse(BikeResponse):
    # The same bike, plus one offer per shop that carries the same SKU
    # (cheapest in-stock variant per shop), sorted cheapest first.
    offers: list[OfferResponse] = []
    lowest_price: float | None = None
    shop_count: int = 0
    # Other frame sizes of the same model (cheapest listing per size).
    variants: list[VariantResponse] = []


class PricePoint(BaseModel):
    observed_at: datetime
    price_sale: float
    price_original: float | None = None

    model_config = {"from_attributes": True}


class FiltersResponse(BaseModel):
    categories: list[str]
    cities: list[str]
    sizes: list[str]
    vendors: list[str]
    brands: list[str]
    frame_materials: list[str]
    drivetrain_groupsets: list[str]
    discount_range: dict
    price_range: dict
    total_bikes: int
    last_scraped_at: datetime | None


class StatsResponse(BaseModel):
    new_today: int
    shops_tracked: int
    biggest_discount: int
    avg_discount: int


class SubscribeRequest(BaseModel):
    email: EmailStr


class UnsubscribeRequest(BaseModel):
    token: str


class MessageResponse(BaseModel):
    message: str


class MarketPoint(BaseModel):
    """One aggregated cell, in the shape every market chart shares.

    Deliberately generic so the eight aggregations behind /meta/market can be
    one UNION ALL and one response model: ``chart`` says which chart the row
    belongs to, ``bucket`` is its x-axis value and ``series`` the stacked or
    coloured dimension. ``n`` is a count of collapsed listings; ``value``
    carries the average where a chart needs one and is null otherwise.
    """

    chart: str
    bucket: str
    # Server-owned sort order. Emitted so a client never has to keep its own
    # copy of the price-band list in sync with ours.
    bucket_rank: int
    series: str
    n: int
    value: float | None = None


class MarketResponse(BaseModel):
    total_listings: int
    # Per-field counts of listings where the shop actually published the
    # attribute. The page needs these to label the enrichment charts honestly:
    # only the Shopify pipeline fills frame_material/drivetrain_groupset, and
    # only when the shop wrote the word in its description.
    coverage: dict[str, int]
    points: list[MarketPoint]
