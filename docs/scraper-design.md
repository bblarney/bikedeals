# Scraper Design

## Vendor registry

Each supported shop is defined as a vendor config entry:

```python
class VendorConfig(BaseModel):
    vendor_name: str
    city: str                   # e.g. "Seattle" — denormalized onto every bike row
    base_url: str
    pipeline: Literal["shopify", "woocommerce", "custom"]
    category_map: dict[str, str]  # shop tag → our category
    # Pipeline B only:
    selectors: dict[str, str] | None = None
```

The registry is a YAML or JSON file checked into the repo. Adding a new shop = adding one entry; no code change required for standard pipelines.

---

## Pipeline A — Shopify / BigCommerce

```
GET {base_url}/products.json?limit=250&page={n}
```

Iterate pages until the response returns fewer than 250 products.

### Field mapping

| Shopify field | Our field |
|---|---|
| `vendor` | `brand` |
| `title` | `model_name` |
| `product_type` / tags | `category` (via `category_map`) |
| `variants[].title` | `frame_size` |
| `variants[].price` | `price_sale` |
| `variants[].compare_at_price` | `price_original` |
| `variants[].available` | `in_stock` |
| `images[0].src` | `image_url` |
| `handle` | used to build `product_url` |

Each variant in `variants[]` becomes a separate row. Skip variants where `title` is a colour or non-size attribute (e.g. "Default Title").

### Shopify detection

A shop runs Shopify if `/products.json` returns HTTP 200 with a `products` key. No need for manual flagging in the vendor registry if you auto-detect.

---

## Pipeline B — WooCommerce / custom HTML

DOM-targeted micro-scrapers. Each shop has its own selector config in the vendor registry.

```python
selectors = {
    "product_list": "ul.products li.product",
    "model_name":   ".woocommerce-loop-product__title",
    "price_sale":   ".price ins .amount",
    "price_original": ".price del .amount",
    "product_url":  "a.woocommerce-LoopProduct-link",
    "image_url":    "img.attachment-woocommerce_thumbnail",
    "frame_size":   ".variation-size",  # may be absent
}
```

These selectors will break when shops redesign. This is expected. Handle it via the quarantine mechanism below.

---

## Rate limiting

Small local bike shops run on shared hosting. Be a polite scraper:

- **Delay between requests:** 1–2 seconds random jitter.
- **Concurrent requests per vendor:** max 2.
- **User-Agent:** Set a descriptive UA: `BikeDeals-Scraper/1.0 (+https://bikedeals.example.com)`.
- **robots.txt:** Check and respect `robots.txt` for each domain before scraping. Log a warning and skip if disallowed; do not scrape anyway.

```python
async def scrape_vendor(config: VendorConfig, client: httpx.AsyncClient):
    await asyncio.sleep(random.uniform(1.0, 2.0))
    # ...
```

---

## Quarantine mechanism

A quarantined scraper is one that has raised an unhandled exception (network error, selector not found, schema validation failure). It must not write any data to the database for that run.

```
scrape_vendor(config)
  └─ raises → log exception with vendor_name, timestamp, error detail
            → append to quarantine_log table or file
            → continue to next vendor (never crash the whole run)
            → trigger alert if N consecutive failures
```

### Quarantine table

```sql
CREATE TABLE scrape_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_name TEXT NOT NULL,
    run_at      TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('ok', 'quarantined', 'skipped')),
    error_msg   TEXT,
    bikes_upserted INTEGER DEFAULT 0
);
```

Alert when `status = 'quarantined'` for the same vendor in 3 consecutive runs. This is the only alerting condition that justifies waking someone up.

---

## Alerting (unresolved in original plan)

The original plan says "logs an alert" with no destination. Options:

| Method | Cost | Complexity |
|---|---|---|
| Email via `smtplib` or SendGrid | Free tier | Low |
| Slack webhook | Free | Low |
| GitHub Actions job failure | Free (native) | Lowest — job fails, GitHub notifies you by email |
| PagerDuty / Opsgenie | Paid | High — overkill for this |

**Recommendation for early stage:** Let GitHub Actions job failure be the primary alert. If the scraper process exits non-zero, GHA emails you. Add a Slack webhook when that feels insufficient.

---

## UPSERT / deduplication

Daily runs must UPSERT, not INSERT. If a product already exists (matched by `id`), update price and stock. If it's new, insert it.

```sql
-- SQLite
INSERT INTO bikes (...) VALUES (...)
ON CONFLICT(id) DO UPDATE SET
    price_sale = excluded.price_sale,
    price_original = excluded.price_original,
    discount_percentage = excluded.discount_percentage,
    in_stock = excluded.in_stock,
    last_seen_at = excluded.last_seen_at;
```

PostgreSQL uses `ON CONFLICT DO UPDATE` with the same syntax.

### Stale product handling

After each vendor's scrape completes successfully, mark any row for that vendor that was NOT in the current run's result set:

```sql
UPDATE bikes
SET in_stock = 0
WHERE vendor_name = :vendor
  AND last_seen_at < :run_start_time;
```

Do not delete rows. Keep them for price history and to avoid confusing users who bookmarked a URL.

---

## Category normalization

This is the hardest part of normalization and it's completely missing from the original plan.

Shop tags are free-form. Examples seen in the wild:
- "road", "Road Bikes", "ROAD CYCLING", "drop-bar", "endurance road"
- "mtb", "Mountain Bikes", "trail", "full-suspension", "hardtail"

The `category_map` in the vendor registry handles this per-shop:

```yaml
# vendors/trek-seattle.yaml
category_map:
  road: Road
  road bikes: Road
  mountain: Mountain
  mtb: Mountain
  trail: Mountain
  gravel: Gravel
  e-bike: E-Bike
  electric: E-Bike
  commuter: Commuter
  city: Commuter
```

For products with no matching tag, default to a special `category = "Other"` (add to the enum) or drop the record and log it. Do **not** silently assign a wrong category.

**Alternative — ML classification:** Use a small embedding model to classify `model_name + tags` into the category enum. More robust but adds complexity. Not recommended until the manual map fails repeatedly.

---

## Scraper run orchestration

```
run_scrapers.py
  ├─ load vendor registry
  ├─ for each vendor (async, max 5 concurrent):
  │     ├─ select pipeline (A or B)
  │     ├─ scrape → List[BikeRecord]
  │     ├─ validate each record (pydantic)
  │     ├─ UPSERT to DB
  │     └─ write scrape_log entry
  └─ mark stale records for all successfully-scraped vendors
```

Run time target: under 10 minutes for 20 shops. GitHub Actions free tier allows 6-hour jobs; well within budget.
