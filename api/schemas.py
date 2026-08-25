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
    # How many of *this* vendor's storefronts carry the listing. A chain lists
    # one national catalogue per city, so those rows collapse to a single result
    # and this is what lets the card still say "at 8 stores". Always 1 once the
    # feed is filtered to a city.
    location_count: int = 1

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
