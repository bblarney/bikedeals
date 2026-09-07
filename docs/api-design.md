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
| `GET` | `/api/v1/vendors` | Per-shop listing and discount counts, for the shops tab |
| `POST` | `/api/v1/subscribe` | Newsletter signup (201) |
| `POST` | `/api/v1/unsubscribe` | Newsletter removal by token |
| `GET` | `/sitemap.xml` | The landing pages, guides and shop pages, for crawlers. Bike pages are deliberately omitted (see the endpoint's comment) |

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
| `sort` | enum | `discount_desc` | `discount_desc` \| `saving_desc` \| `price_asc` \| `price_desc` \| `clicks_desc` |
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
      "sku_vendor_count": 3,
      "location_count": 1,
      "sizes": ["S", "M", "L"]
    }
  ]
}
```

**One result is one product at one vendor, not one row per variant.** The feed
collapses twice, in this order:

1. **Chain storefronts.** A vendor with a `cities:` list produces one row per
   city for the same national catalogue. They collapse to the cheapest, which
   carries `location_count` — how many of that vendor's storefronts stock it.
2. **Size and colour variants.** A shop publishes each size (and on Shopify each
   colourway) as its own `?variant=` URL. They collapse to the cheapest, which
   carries `sizes` — every size behind the card, smallest first.

Together these removed 49% of the rows measured over 2,000 live listings sorted
`discount_desc`: page one was six consecutive cards of one Giant Revolt, and one
Bikes Online product held 13 rows that were three sizes in assorted colours.

Two products are only merged when they agree on vendor **and** brand **and**
model_name **and** URL path — the intersection of the two identities the
codebase already uses, so the collapse can never merge rows the rest of the API
treats as different products.

Both counts describe the **filtered** catalogue, not the whole one: `?city=`
leaves `location_count` at 1, and `?size=L` leaves `sizes` as `["L"]`. A
filtered feed answers questions about what it is showing.

`sizes` is empty when the shop published nothing usable (`One Size`, `N/A`).
It is feed-only — the detail endpoint returns the richer `variants` instead.

`sku_vendor_count` is the number of distinct **vendors** (not storefronts)
carrying that product in stock, and is `0` unless at least two vendors carry it
— it drives the "available at N shops" badge. Grouping is on `product_key`, not
`sku`; counting is per vendor, not per storefront. See
[`data-model.md`](data-model.md) for why both matter.

Each entry in `offers` carries `location_count` on the same rule.

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

`saving_desc` ranks on dollars off rather than percent off, which is a different
question: 20% off a $13,000 bike is $2,600, and 60% off a $600 one is $360. It is
an expression (`coalesce(price_original, price_sale) - price_sale`) rather than a
stored column. The coalesce is load-bearing: `price_original` is null on anything
never discounted, and Postgres sorts nulls first on a DESC order, so without it a
full-price bike would head a feed sorted by biggest saving.

---

### `GET /api/v1/meta/filters`

Returns filter options. **Facets are computed with all *other* active filters
applied** — each facet excludes itself, so selecting a brand narrows the size list
but leaves the brand list intact. Accepts the same filter params as `/bikes`
(minus `sort`, `limit`, `offset`, `in_stock`, `sku`).

Range filters (`min_price`, `max_price`, `min_discount`) deliberately do **not**
narrow the discrete facets — an out-of-range price shouldn't wipe out the
category list. `price_range` is the slider's *bounds* and likewise ignores
`min_price`/`max_price`, or a narrowed selection could never be widened again.

**All seven facets are one `UNION ALL` statement**, labelled per branch and
split apart in Python. This endpoint is round-trip bound, not scan bound: it
issued eleven sequential statements and took ~0.8s in production against a
remote Postgres, while `/bikes` — doing real work over the same table — took
~0.28s. Four round trips remain (facets, the discount range plus total, the
price range, and the last scrape time), and `/bikes` and `/meta/filters` are
now within ~40ms of each other.

An earlier note here explained that `asyncio.gather` could not parallelise the
facets because an async session serializes within its connection. True, but the
wrong target: removing the round trips beats overlapping them, and it needs no
extra connections from the pool. `tests/test_api.py` asserts the round-trip
budget so a future facet cannot quietly add a query.

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

### `GET /api/v1/vendors`

Every shop with stock, and how much of its range is currently discounted. Backs
both `/shops` and `/shops/<slug>`: the payload is one row per shop (~100), so the
shop page reads this same cached response rather than paying for an endpoint of
its own, which is also what lets it show its rank among its neighbours.

```json
{ "vendors": [
  { "vendor_name": "Bike Zone Fitzroy", "listings": 93, "on_sale": 81,
    "deepest_cut": 69, "last_success_at": "2026-08-29T13:36:11Z" }
] }
```

Counted on `_VARIANT_GROUP`, the same collapse `/meta/filters` uses for its
total, so a shop's `listings` matches what `/bikes?vendor=` returns. Counting raw
rows would report a chain's catalogue once per city: 99 Bikes would claim roughly
eight times its real range on a page whose entire job is comparing shops.

`last_success_at` comes from a LEFT join on `scrape_log`, so a vendor with stock
but no log row still appears, just without a checked-at time.

**No city is returned, deliberately.** A chain stores one catalogue row per city,
so filtering these counts by city would not narrow them, and a per-city count
would read as local stock when it is nothing of the kind. Which cities a shop
trades in comes from the YAML registry via `frontend/src/content/shops.js`, and
the UI ranks local storefronts separately from the national sellers that merely
deliver there.

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
| `/api/v1/vendors` | `max-age=300` |
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
