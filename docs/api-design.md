# API Design

Reflects `api/main.py` and `api/schemas.py`. When the code and this document
disagree, the code wins — please fix the document.

## Design principles

- **Read-mostly.** The scraper owns all bike data. The API accepts three small
  writes — a click counter and newsletter subscribe/unsubscribe — and nothing else.
- **No auth.** Public API, protected by per-IP rate limits rather than keys.
- **Thin.** Filtering, sorting, and pagination happen in SQL, not in Python.
- **CORS restricted.** An explicit origin allowlist, not `*` (see below).

---

## Base URL

```
/api/v1/
```

`GET /sitemap.xml` is served from the root, outside the versioned prefix.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Liveness + DB connectivity |
| `GET` | `/api/v1/bikes` | Main deal feed |
| `GET` | `/api/v1/bikes/{bike_id}` | One deal, plus cross-shop offers and size variants |
| `GET` | `/api/v1/bikes/{bike_id}/price-history` | Price change-events for the chart |
| `POST` | `/api/v1/bikes/{bike_id}/click` | Increment the click counter (204) |
| `GET` | `/api/v1/meta/filters` | Faceted filter options |
| `GET` | `/api/v1/meta/stats` | Headline counters for the landing page |
| `POST` | `/api/v1/subscribe` | Newsletter signup (201) |
| `POST` | `/api/v1/unsubscribe` | Newsletter removal by token |
| `GET` | `/sitemap.xml` | One entry per in-stock bike, for crawlers |

---

### `GET /api/v1/bikes`

Main deal feed. **Every filter below marked "repeatable" accepts multiple values
and ORs them** (`?category=Road&category=Gravel`).

| Param | Type | Default | Description |
|---|---|---|---|
| `category` | string (repeatable) | — | `Road`, `Mountain`, `Gravel`, `E-Bike`, `Commuter` |
| `city` | string (repeatable) | — | Case-insensitive match |
| `size` | string (repeatable) | — | `frame_size` |
| `vendor` | string (repeatable) | — | `vendor_name` |
| `brand` | string (repeatable) | — | |
| `frame_material` | string (repeatable) | — | |
| `drivetrain_groupset` | string (repeatable) | — | |
| `min_discount` | int 0–100 | 0 | Minimum `discount_percentage` |
| `min_price` / `max_price` | float ≥ 0 | — | On `price_sale` |
| `in_stock` | bool | `true` | `false` includes out-of-stock |
| `q` | string (≤100 chars) | — | Case-insensitive `LIKE` on brand **or** model_name |
| `added_since` | enum | — | `day` \| `week` \| `month` \| `year`, on `scraped_at` |
| `product_key` | string | — | Every listing of one product, across shops |
| `sku` | string | — | Exact SKU match. Deprecated: collides across brands — prefer `product_key` |
| `sort` | enum | `discount_desc` | `discount_desc` \| `price_asc` \| `price_desc` \| `clicks_desc` |
| `limit` | int 1–200 | 50 | |
| `offset` | int ≥ 0 | 0 | |

Out-of-range values are rejected by FastAPI validation with a `422`, not clamped.

`added_since` quantizes "now" to the top of the hour so identical requests within
an hour share a cache key and a query plan.

**Response** — `PaginatedBikes`:

```json
{
  "total": 342,
  "limit": 50,
  "offset": 0,
  "results": [
    {
      "id": "a1b2c3d4e5f6a7b8",
      "vendor_name": "Local Bike Shop",
      "city": "Melbourne",
      "brand": "Trek",
      "model_name": "Marlin 5",
      "category": "Mountain",
      "frame_size": "M",
      "price_original": 699.00,
      "price_sale": 499.00,
      "discount_percentage": 29,
      "in_stock": true,
      "product_url": "https://localshop.com.au/products/trek-marlin-5?variant=123",
      "image_url": "https://cdn.localshop.com.au/trek-marlin-5.jpg",
      "scraped_at": "2026-08-04T08:30:00Z",
      "last_seen_at": "2026-08-05T08:30:00Z",
      "click_count": 12,
      "price_drop_at": null,
      "discount_started_at": null,
      "frame_material": "Aluminium",
      "drivetrain_groupset": "Shimano Deore",
      "sku": "5259601",
      "sku_vendor_count": 3
    }
  ]
}
```

`sku_vendor_count` is the number of distinct **vendors** (not storefronts)
carrying that product in stock, and is `0` unless at least two vendors carry it
— it drives the "available at N shops" badge. Grouping is on `product_key`, not
`sku`; counting is per vendor, not per storefront. See
[`data-model.md`](data-model.md) for why both matter.

Each entry in `offers` carries `location_count`: how many of that vendor's
storefronts stock the product. Chains collapse to one row (one catalogue, one
price) but still report their reach.

**Affiliate links:** `product_url` is rewritten for vendors configured in
`_AFFILIATE_URLS` (currently Bikes Online, via `IMPACT_BIKESONLINE_URL`). The
original URL is passed as a `u=` query param. Unconfigured vendors are untouched.

---

### `GET /api/v1/bikes/{bike_id}`

Everything in `BikeResponse` plus:

- `offers` — every in-stock listing sharing this bike's SKU, collapsed to the
  cheapest variant **per shop**, cheapest first. A bike with no SKU stands alone.
- `shop_count` / `lowest_price` — derived from `offers`.
- `variants` — other frame sizes of the same `(brand, model_name)`, cheapest
  listing per size.

`404` if the ID is unknown.

---

### `GET /api/v1/bikes/{bike_id}/price-history`

Returns `[{observed_at, price_sale, price_original}]` ascending by time. These are
**change-events, not daily snapshots** — a flat line means the price genuinely
didn't move. `404` on an unknown bike, so the chart can distinguish "no such
deal" from "no recorded changes yet".

---

### `POST /api/v1/bikes/{bike_id}/click`

Increments `click_count`. Returns `204` with no body; `404` if unknown. Feeds the
`clicks_desc` sort.

---

### `GET /api/v1/meta/filters`

Returns filter options. **Facets are computed with all *other* active filters
applied** — each facet excludes itself, so selecting a brand narrows the size list
but leaves the brand list intact. Accepts the same filter params as `/bikes`
(minus `sort`, `limit`, `offset`, `in_stock`, `sku`).

Range filters (`min_price`, `max_price`, `min_discount`) deliberately do **not**
narrow the discrete facets — an out-of-range price shouldn't wipe out the
category list.

```json
{
  "categories": ["Gravel", "Mountain", "Road"],
  "cities": ["Adelaide", "Brisbane", "Melbourne", "Perth", "Sydney"],
  "sizes": ["L", "M", "S", "XL", "XS"],
  "vendors": ["Bike Line", "Crooze", "Hendry's"],
  "brands": ["Giant", "Merida", "Trek"],
  "frame_materials": ["Aluminium", "Carbon"],
  "drivetrain_groupsets": ["Shimano 105", "Shimano Deore"],
  "discount_range": { "min": 5, "max": 60 },
  "price_range": { "min": 299.0, "max": 12999.0 },
  "total_bikes": 342,
  "last_scraped_at": "2026-08-05T08:30:00Z"
}
```

`last_scraped_at` is `MAX(run_at)` from `scrape_log` where `status = 'ok'`.

> **Known limitation:** the facet queries run sequentially. SQLAlchemy's async
> session serializes within one connection, so `asyncio.gather` raises
> `InvalidRequestError` here; real concurrency needs separate sessions from the
> pool. Fine at current row counts.

---

### `GET /api/v1/meta/stats`

Landing-page counters, all over in-stock bikes:
`new_today` (scraped in the last 24h), `shops_tracked`, `biggest_discount`,
`avg_discount` (mean over discounted bikes only).

---

### `GET /api/v1/health`

```json
{"status": "ok", "database": "connected"}
```

Executes `SELECT 1`. On failure returns **503** with
`{"status": "degraded", "database": "unreachable"}` — so a platform health check
correctly fails when the DB is down rather than reporting a healthy process.

---

### `POST /api/v1/subscribe` · `POST /api/v1/unsubscribe`

Subscribe takes `{"email": ...}`, returns `201`, and `409` if already subscribed.
A `secrets.token_urlsafe(32)` unsubscribe token is generated per subscriber.

Unsubscribe takes `{"token": ...}` and returns `404` for an unknown token. It is
**POST, not GET, on purpose**: email clients and CDNs prefetch links, which would
silently unsubscribe people, and a GET would leak the token into proxy logs.

---

## Rate limiting

Per-IP via `slowapi` (`get_remote_address`), applied per route:

| Route | Limit |
|---|---|
| Read endpoints (`/bikes`, `/meta/*`, price history) | 120/minute |
| `/bikes/{id}/click` | 30/minute |
| `/sitemap.xml` | 30/minute |
| `/unsubscribe` | 10/minute |
| `/subscribe` | 5/minute |

Exceeding a limit returns `429` via slowapi's handler.

---

## Error format

Two shapes, and it's worth knowing which is which:

**Unhandled exceptions (500)** use the envelope, with the traceback logged
server-side and never returned:

```json
{"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred."}}
```

**Everything else** uses FastAPI's default `{"detail": "..."}` — `404` from
`HTTPException`, `422` from query-param validation, `429` from slowapi. Clients
must handle both.

| Status | When |
|---|---|
| `404` | Unknown `bike_id`, unknown unsubscribe token |
| `409` | Email already subscribed |
| `422` | Query param failed validation |
| `429` | Rate limit exceeded |
| `500` | Unhandled error (envelope form, detail scrubbed) |

---

## CORS

Not `*`. An explicit allowlist, overridable per environment:

```python
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://bikegrid.com.au,https://www.bikegrid.com.au",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept", "Origin"],
)
```

`POST` is allowed because of the click and subscribe endpoints. Local dev goes
through the Vite proxy, so it is same-origin and needs no CORS entry.

---

## Caching

Shorter than the original plan's blanket hour — the feed changes after each
scrape, and filter options change whenever a vendor is added.

| Endpoint | Cache-Control |
|---|---|
| `/api/v1/bikes`, `/bikes/{id}`, price history | `max-age=300` |
| `/api/v1/meta/filters` | `max-age=60` |
| `/api/v1/meta/stats` | `max-age=300` |
| `/sitemap.xml` | `max-age=3600` |
| `/api/v1/health` | none |

---

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy async URL; required |
| `ALLOWED_ORIGINS` | Comma-separated CORS allowlist |
| `SITE_URL` | Public frontend origin, used to build absolute sitemap URLs |
| `IMPACT_BIKESONLINE_URL` | Affiliate base URL for Bikes Online; unset disables rewriting |
| `LOG_LEVEL` | Defaults to `INFO` |

---

## Schema ownership

`Base.metadata.create_all` runs **only on SQLite**, as a zero-setup dev
convenience. On Postgres, Alembic owns the schema (`alembic upgrade head`) —
calling `create_all` there creates tables outside Alembic's tracking and the next
migration fails with `DuplicateTableError`. `api/main.py` and `scrapers/run.py`
both guard this the same way.
