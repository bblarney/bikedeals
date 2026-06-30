from datetime import datetime

from pydantic import BaseModel, EmailStr


class BikeResponse(BaseModel):
    id: str
    vendor_name: str
    city: str | None
    brand: str
    model_name: str
    category: str
    frame_size: str
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
    sku_vendor_count: int = 0

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
