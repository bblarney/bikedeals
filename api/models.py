from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    Text,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Bike(Base):
    __tablename__ = "bikes"

    id = Column(Text, primary_key=True)
    vendor_name = Column(Text, nullable=False)
    city = Column(Text, nullable=True)
    brand = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    frame_size = Column(Text, nullable=False)
    price_original = Column(Float, nullable=True)
    price_sale = Column(Float, nullable=False)
    discount_percentage = Column(Integer, nullable=False, default=0)
    in_stock = Column(Boolean, nullable=False, default=True)
    product_url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    scraped_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    click_count = Column(Integer, nullable=False, default=0, server_default="0")
    sku = Column(Text, nullable=True)
    weight_grams = Column(Integer, nullable=True)
    product_updated_at = Column(DateTime(timezone=True), nullable=True)
    tags = Column(JSON, nullable=True)
    frame_material = Column(Text, nullable=True)
    drivetrain_groupset = Column(Text, nullable=True)
    price_drop_at = Column(DateTime(timezone=True), nullable=True)
    discount_started_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "category IN ('Road','Mountain','Gravel','E-Bike','Commuter')",
            name="chk_category",
        ),
        CheckConstraint("price_sale > 0", name="chk_price"),
        CheckConstraint(
            "discount_percentage >= 0 AND discount_percentage <= 100",
            name="chk_discount",
        ),
        Index("idx_bikes_category", "category"),
        Index("idx_bikes_frame_size", "frame_size"),
        Index("idx_bikes_vendor", "vendor_name"),
        Index("idx_bikes_city", "city"),
        Index("idx_bikes_brand", "brand"),
        Index("idx_bikes_discount_desc", "discount_percentage"),
        Index("idx_bikes_in_stock", "in_stock"),
        Index("idx_bikes_click_count", "click_count"),
        Index("idx_bikes_scraped_at", "scraped_at"),
    )


class ScrapeLog(Base):
    __tablename__ = "scrape_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vendor_name = Column(Text, nullable=False)
    run_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Text, nullable=False)  # 'ok' | 'quarantined' | 'skipped'
    error_msg = Column(Text, nullable=True)
    bikes_upserted = Column(Integer, default=0)


class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(Text, nullable=False, unique=True)
    token = Column(Text, nullable=False, unique=True)
    subscribed_at = Column(DateTime(timezone=True), nullable=False)
