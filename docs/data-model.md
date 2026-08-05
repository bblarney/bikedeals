# Data Model

`api/models.py` holds the canonical SQLAlchemy definitions — both the API and the
scraper import from there, and Alembic migrations in `migrations/` track changes
to it. `scrapers/models.py` holds the Pydantic models the scrapers produce. When
the code and this document disagree, the code wins.

## Tables

Four: `bikes`, `price_events`, `scrape_log`, `subscribers`.

---

## `bikes`

```python
class BikeRecord(BaseModel):        # scrapers/models.py — what a pipeline emits
    id: str                         # sha256(vendor_name::city::product_url::frame_size)[:16]
    vendor_name: str
    city: str | None                # nullable: chains fan out, some vendors are national
    brand: str
    model_name: str
    category: Literal["Road", "Mountain", "Gravel", "E-Bike", "Commuter"]
    frame_size: str                 # one row per size variant; "N/A" if the shop declares none
    price_original: float | None    # AUD; None if never listed at a compare_at price
    price_sale: float               # AUD
    discount_percentage: int        # recomputed on every UPSERT, stored for indexing
    in_stock: bool
    product_url: str
    image_url: str | None
    scraped_at: datetime
    last_seen_at: datetime
    sku: str | None                 # cross-shop matching key
    weight_grams: int | None
    product_updated_at: datetime | None
    tags: list[str] | None
    frame_material: str | None
    drivetrain_groupset: str | None
```

Three further `bikes` columns are not fields on `BikeRecord`:

- `click_count` — owned by the API, incremented by `POST /bikes/{id}/click`.
- `price_drop_at` / `discount_started_at` — derived by the scraper *during* the
  UPSERT rather than carried on the record, because both need the previous row to
  compute: `price_drop_at` advances only when the new sale price is lower, and
  `discount_started_at` is set when a discount first appears. Otherwise the
  existing value is preserved, so the badges survive daily re-scrapes.

### ID strategy

```python
def make_bike_id(vendor_name, product_url, frame_size, city=None) -> str:
    key = f"{vendor_name}::{city or ''}::{product_url}::{frame_size}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

Deterministic hash, so IDs survive re-scrapes, restarts and database rebuilds.
Each component earns its place:

- **`product_url`** rather than `model_name` — URLs are canonical per shop, model
  names drift with typos, casing and punctuation.
- **`frame_size`** — one row per size variant, so sizes must not collide.
- **`city`** — a national chain fans one product out to one record per city; without
  city in the key those rows would collapse onto a single ID.

16 hex chars is 64 bits; collision risk is negligible at this scale.

### `sku` and cross-shop comparison

Where a shop publishes a manufacturer SKU, it is the join key for "the same bike
at other shops". A *shop* is the pair **(vendor_name, city)** — `vendor_name`
alone is not unique, because chains share one name across locations. Both the
feed's `sku_vendor_count` and the detail page's `offers` list group on that pair.

### No `UNIQUE(product_url)`

An earlier draft of this document specified one. It is deliberately absent: one
product URL legitimately produces several rows (one per frame size), and for
chains, one per city as well. Deduplication is the `id` primary key's job.

### Variants

One row per size variant. Frame size comes from the platform's declared size axis
(for Shopify, `product.options`, preferring "Frame Size" over "Wheel Size") — never
from parsing the variant title, which is how colours like "Forge Grey" end up in
the size filter. A product with no size axis records `"N/A"` and is kept.

The frontend groups rows by model so users see one card per bike rather than five
near-identical cards differing only by size.

### Null pricing

Shopify's `compare_at_price` is null for products never discounted:

- `price_original = None` → `discount_percentage = 0`; the item still appears, just
  doesn't rank at the top.
- `price_original == price_sale` → treated as no discount.
- `price_sale > price_original` → data error. The `BikeRecord` validator rejects it,
  the record is counted as invalid, and >5% invalid quarantines the vendor.

### Timestamps

| Field | Meaning |
|---|---|
| `scraped_at` | Scrape run that first inserted this record |
| `last_seen_at` | Most recent run that found it still present |
| `product_updated_at` | The shop's own last-modified value, where published |
| `price_drop_at` / `discount_started_at` | When the price last fell / the current discount began — drives the "price drop" and "new deal" badges |

A product missing from a feed is marked `in_stock = false` via `last_seen_at <
run_start`. Rows are **never deleted** — price history and bookmarked URLs depend
on them. That marking is skipped entirely when a vendor scrape fails or returns
zero bikes, so a transient outage can't flag a whole shop out of stock.

### Image URLs

Point at shop CDNs and will break. Current policy is to accept breakage and render
a placeholder; validating each URL with a HEAD request on scrape is the next step
if it becomes a visible problem, and re-hosting is not planned.

---

## `price_events`

```sql
CREATE TABLE price_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    bike_id        TEXT NOT NULL,        -- references bikes.id (no hard FK, per existing style)
    price_sale     REAL NOT NULL,
    price_original REAL,
    observed_at    TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_price_events_bike_observed ON price_events(bike_id, observed_at);
```

A row is appended **only when a bike is first seen or its sale price changes** —
not a daily snapshot. That keeps the table flat enough for the free-tier storage
cap while still backing a real timeline. Events older than
`PRICE_EVENT_RETENTION_DAYS` (default 365) are pruned at the end of each run.

Consequence for consumers: a flat line on the chart means the price genuinely
didn't move, not that data is missing.

---

## `scrape_log`

```sql
CREATE TABLE scrape_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_name     TEXT NOT NULL UNIQUE,   -- one current row per vendor
    run_at          TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL,          -- ok | quarantined | skipped | empty
    error_msg       TEXT,
    bikes_upserted  INTEGER DEFAULT 0,
    last_success_at TIMESTAMPTZ
);
```

Upserted per vendor rather than appended, so the table holds current state, not
history. `last_success_at` only advances on `ok`, which makes "how long has this
vendor been broken?" answerable from a single row.

---

## `subscribers`

`id`, `email` (unique), `token` (unique, `secrets.token_urlsafe(32)`),
`subscribed_at`. The token is the unsubscribe credential.

---

## DDL — `bikes`

```sql
CREATE TABLE bikes (
    id                  TEXT PRIMARY KEY,
    vendor_name         TEXT NOT NULL,
    city                TEXT,
    brand               TEXT NOT NULL,
    model_name          TEXT NOT NULL,
    category            TEXT NOT NULL,
    frame_size          TEXT NOT NULL,
    price_original      REAL,
    price_sale          REAL NOT NULL,
    discount_percentage INTEGER NOT NULL DEFAULT 0,
    in_stock            BOOLEAN NOT NULL DEFAULT 1,
    product_url         TEXT NOT NULL,
    image_url           TEXT,
    scraped_at          TIMESTAMPTZ NOT NULL,
    last_seen_at        TIMESTAMPTZ NOT NULL,
    click_count         INTEGER NOT NULL DEFAULT 0,
    sku                 TEXT,
    weight_grams        INTEGER,
    product_updated_at  TIMESTAMPTZ,
    tags                JSON,
    frame_material      TEXT,
    drivetrain_groupset TEXT,
    price_drop_at       TIMESTAMPTZ,
    discount_started_at TIMESTAMPTZ,

    CONSTRAINT chk_category CHECK (category IN ('Road','Mountain','Gravel','E-Bike','Commuter')),
    CONSTRAINT chk_price    CHECK (price_sale > 0),
    CONSTRAINT chk_discount CHECK (discount_percentage >= 0 AND discount_percentage <= 100)
);

CREATE INDEX idx_bikes_category         ON bikes(category);
CREATE INDEX idx_bikes_frame_size       ON bikes(frame_size);
CREATE INDEX idx_bikes_vendor           ON bikes(vendor_name);
CREATE INDEX idx_bikes_city             ON bikes(city);
CREATE INDEX idx_bikes_brand            ON bikes(brand);
CREATE INDEX idx_bikes_discount_desc    ON bikes(discount_percentage);
CREATE INDEX idx_bikes_in_stock         ON bikes(in_stock);
CREATE INDEX idx_bikes_click_count      ON bikes(click_count);
CREATE INDEX idx_bikes_scraped_at       ON bikes(scraped_at);
CREATE INDEX idx_bikes_sku              ON bikes(sku);
CREATE INDEX idx_bikes_cat_size_vendor  ON bikes(category, frame_size, vendor_name);
CREATE INDEX idx_bikes_instock_discount ON bikes(in_stock, discount_percentage);
```

The last two composites serve the common feed query: filter by
category/size/vendor, or by stock status sorted on discount.

---

## Migrations

Alembic owns the Postgres schema; `migrations/` holds the revisions and
`alembic upgrade head` runs before the scraper in CI.

`Base.metadata.create_all` is restricted to SQLite in both `api/main.py` and
`scrapers/run.py`. Running it against Postgres creates *tables* outside Alembic's
tracking but never applies altered columns or constraints, which silently drifts
prod until the next migration fails. Schema changes go through Alembic — always.
