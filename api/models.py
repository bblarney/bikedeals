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
    UniqueConstraint,
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
    # What the shop called the size, verbatim. Stays the id-bearing value —
    # make_bike_id hashes it — so normalising sizes cannot change a bike's id.
    frame_size = Column(Text, nullable=False)
    # The same size on a shared scale ("L", "54cm", "16\""), or NULL when the
    # raw value names no usable size ("N/A", "One Size", "Chrome Blue"). This is
    # what the size filter and the size facet read; see
    # scrapers.utils.canonical_frame_size.
    frame_size_canonical = Column(Text, nullable=True)
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
    # Cross-shop product identity: "<normalised brand>:<sku>", NULL when the
    # shop publishes no SKU. Grouping on this instead of sku is what keeps two
    # unrelated products that share a POS counter from being merged into one
    # listing. Written by the scraper — see scrapers.models.make_product_key.
    product_key = Column(Text, nullable=True)

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
        Index("idx_bikes_frame_size_canonical", "frame_size_canonical"),
        Index("idx_bikes_vendor", "vendor_name"),
        Index("idx_bikes_city", "city"),
        Index("idx_bikes_brand", "brand"),
        Index("idx_bikes_discount_desc", "discount_percentage"),
        Index("idx_bikes_in_stock", "in_stock"),
        Index("idx_bikes_click_count", "click_count"),
        Index("idx_bikes_scraped_at", "scraped_at"),
        # Cross-shop comparison: grouped per /bikes call and filtered by the
        # detail/offers endpoint.
        Index("idx_bikes_sku", "sku"),
        Index("idx_bikes_product_key", "product_key"),
        # Composite indexes for the common multi-filter feed query
        # (CLAUDE.md: filter by category/size/vendor, sort by discount desc).
        Index("idx_bikes_cat_size_vendor", "category", "frame_size_canonical", "vendor_name"),
        Index("idx_bikes_instock_discount", "in_stock", "discount_percentage"),
    )


class ScrapeLog(Base):
    __tablename__ = "scrape_log"

    __table_args__ = (UniqueConstraint("vendor_name", name="uq_scrape_log_vendor"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    vendor_name = Column(Text, nullable=False)
    run_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Text, nullable=False)  # 'ok' | 'quarantined' | 'skipped' | 'empty'
    error_msg = Column(Text, nullable=True)
    bikes_upserted = Column(Integer, default=0)
    last_success_at = Column(DateTime(timezone=True), nullable=True)


class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(Text, nullable=False, unique=True)
    token = Column(Text, nullable=False, unique=True)
    subscribed_at = Column(DateTime(timezone=True), nullable=False)


class PriceEvent(Base):
    """Change-events for a listing's sale price.

    One row is appended only when a bike is first seen or its sale price
    changes (see ``scrapers/db.upsert_bikes``) — not a daily snapshot — so the
    table stays small enough for the free-tier storage cap while still backing a
    real price-history timeline on the detail page.
    """

    __tablename__ = "price_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bike_id = Column(Text, nullable=False)  # references bikes.id (no hard FK, per existing style)
    price_sale = Column(Float, nullable=False)
    price_original = Column(Float, nullable=True)
    observed_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # Per-bike, time-ordered fetch for the price-history endpoint.
        Index("idx_price_events_bike_observed", "bike_id", "observed_at"),
    )
