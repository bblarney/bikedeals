import hashlib
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


def make_bike_id(vendor_name: str, product_url: str, frame_size: str, city: str | None = None) -> str:
    key = f"{vendor_name}::{city or ''}::{product_url}::{frame_size}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


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
    pipeline: Literal["shopify", "woocommerce", "custom"]
    category_map: dict[str, str]
    selectors: dict[str, str] | None = None


class BikeRecord(BaseModel):
    id: str
    vendor_name: str
    city: str | None
    brand: str
    model_name: str
    category: Literal["Road", "Mountain", "Gravel", "E-Bike", "Commuter"]
    frame_size: str
    price_original: float | None
    price_sale: float
    discount_percentage: int
    in_stock: bool
    product_url: str
    image_url: str | None
    scraped_at: datetime
    last_seen_at: datetime

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
    error: str | None = None
