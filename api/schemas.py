from datetime import datetime

from pydantic import BaseModel


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
    last_seen_at: datetime
    click_count: int

    model_config = {"from_attributes": True}


class PaginatedBikes(BaseModel):
    total: int
    limit: int
    offset: int
    results: list[BikeResponse]


class FiltersResponse(BaseModel):
    categories: list[str]
    cities: list[str]
    sizes: list[str]
    vendors: list[str]
    brands: list[str]
    discount_range: dict
    total_bikes: int
    last_scraped_at: datetime | None
