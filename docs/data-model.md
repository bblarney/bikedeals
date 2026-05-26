# Data Model

## Normalized bike schema

```python
class Bike(BaseModel):
    id: str                     # sha256(vendor_name::product_url)[:16]
    vendor_name: str
    city: str                   # Australian city from vendor registry; e.g. "Melbourne"
    brand: str
    model_name: str
    category: Literal["Road", "Mountain", "Gravel", "E-Bike", "Commuter"]
    frame_size: str             # one row per size variant
    price_original: float | None  # AUD; None if never listed at a compare_at price
    price_sale: float             # AUD
    discount_percentage: int    # computed from price_original/price_sale; stored for indexing
    in_stock: bool
    product_url: str
    image_url: str | None
    scraped_at: datetime        # when this record was first inserted
    last_seen_at: datetime      # most recent successful scrape that found this record
```

---

## ID strategy (unresolved in original plan)

The original schema has `"id": "string"` with no guidance. This is the most important design decision in the whole data model — it determines how deduplication works on daily re-scrapes.

### Option A — Deterministic hash (recommended)

```python
import hashlib
id = hashlib.sha256(f"{vendor_name}::{product_url}".encode()).hexdigest()[:16]
```

- Stable across re-scrapes as long as the URL doesn't change.
- Survives restarts and database rebuilds.
- Collision risk with 16 hex chars (64-bit): negligible at this scale.

**Use `product_url` as the key input**, not `model_name + frame_size`, because model names drift (typos, casing, punctuation) while URLs are canonical per shop.

### Option B — Composite primary key

Make `(vendor_name, product_url)` the primary key directly. No hashing. Simpler to debug.

**Tradeoff vs A:** Primary key is a long string; fine for SQLite/Postgres but foreign keys become verbose.

### Option C — Sequential integer + unique constraint

Auto-increment integer PK with a `UNIQUE(vendor_name, product_url)` constraint. Use the integer ID in the API.

**Tradeoff:** The ID exposed in the API is meaningless (doesn't encode shop/product), and you need to look up the constraint to understand dedup logic.

**Recommendation:** Option A for now, Option C if you add relational tables (e.g. a `vendors` table with a proper FK).

---

## Variants

**Decision: one row per size variant.** Consequences:

- **ID generation:** Include `frame_size` in the hash: `sha256(vendor_name::product_url::frame_size)[:16]`. Two rows for the same model in different sizes get different IDs. Use `product_url` as the variant-level URL where Shopify provides one (e.g. `?variant=12345`), otherwise append frame_size to the base URL.
- **Shopify Pipeline A:** `/products.json` returns a `variants` array; iterate it and emit one `Bike` per variant.
- **Display:** The frontend groups rows by `(vendor_name, brand, model_name)` to show one card per model with a size selector, rather than 5 identical cards.

---

## Derived fields

`discount_percentage` can be computed from `price_original` and `price_sale`:

```python
discount_percentage = round((1 - price_sale / price_original) * 100) if price_original else 0
```

**Risk:** Storing it as a column means it can go stale if `price_sale` is updated without recomputing. Two options:

1. Compute it in the scraper and store it (simplest).
2. Use a database computed/generated column (PostgreSQL supports this; SQLite does not).

Given the SQLite → Postgres path, option 1 is safer. Just always recompute during UPSERT.

---

## Null pricing

Shopify's `compare_at_price` is null for products that have never been discounted. This means `price_original` is `None` for non-sale items.

Rules:
- `price_original = None` → `discount_percentage = 0`, item can still appear in results but won't rank at the top.
- `price_original = price_sale` → treat as no discount (shop left compare_at_price populated but didn't actually discount).
- `price_sale > price_original` → data error; log and skip this record.

---

## Timestamps

The original schema has only `last_updated` with no definition of what it means.

Replace with two explicit fields:

| Field | Meaning |
|---|---|
| `scraped_at` | Timestamp of the scrape run that first inserted this record |
| `last_seen_at` | Timestamp of the most recent scrape run that found this record still present |

When a product disappears from a shop's feed:
- Do **not** delete the row immediately (could be a transient outage).
- After N consecutive missed scrapes (e.g. 3 days), mark `in_stock = false` or soft-delete.

---

## Image URLs

Image URLs point to shop CDN servers. They will break when:
- The shop updates the product listing
- The shop migrates their CDN
- The product is discontinued

Options:
1. **Accept breakage** — show a placeholder on 404. Simplest. Fine for early stage.
2. **Validate on scrape** — HEAD request each image URL; mark `image_url = null` if 404.
3. **Proxy/re-host** — Download images and serve from own CDN. Never breaks but adds storage cost.

**Recommendation:** Start with option 1. Add option 2 validation to the scraper once the pipeline is stable.

---

## DDL (SQLite-compatible, SQLAlchemy-ready)

```sql
CREATE TABLE bikes (
    id               TEXT PRIMARY KEY,
    vendor_name      TEXT NOT NULL,
    city             TEXT NOT NULL,
    brand            TEXT NOT NULL,
    model_name       TEXT NOT NULL,
    category         TEXT NOT NULL CHECK (category IN ('Road','Mountain','Gravel','E-Bike','Commuter')),
    frame_size       TEXT NOT NULL,
    price_original   REAL,
    price_sale       REAL NOT NULL,
    discount_percentage INTEGER NOT NULL DEFAULT 0,
    in_stock         INTEGER NOT NULL DEFAULT 1,  -- SQLite has no BOOLEAN
    product_url      TEXT NOT NULL UNIQUE,
    image_url        TEXT,
    scraped_at       TEXT NOT NULL,  -- ISO 8601
    last_seen_at     TEXT NOT NULL,  -- ISO 8601

    CONSTRAINT chk_price CHECK (price_sale > 0),
    CONSTRAINT chk_discount CHECK (discount_percentage >= 0 AND discount_percentage <= 100)
);

CREATE INDEX idx_bikes_category       ON bikes(category);
CREATE INDEX idx_bikes_frame_size     ON bikes(frame_size);
CREATE INDEX idx_bikes_vendor         ON bikes(vendor_name);
CREATE INDEX idx_bikes_city           ON bikes(city);
CREATE INDEX idx_bikes_discount_desc  ON bikes(discount_percentage DESC);
CREATE INDEX idx_bikes_in_stock       ON bikes(in_stock);
```

The `UNIQUE(product_url)` constraint enforces dedup at the database level as a safety net on top of application-level UPSERT logic.
