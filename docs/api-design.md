# API Design

## Design principles

- **Read-only.** No writes through the API; all writes happen via the scraper.
- **No auth.** Public API. Add rate limiting at the reverse proxy level if abuse occurs.
- **Thin wrapper.** No business logic lives here — filtering, sorting, and pagination happen in SQL.
- **CORS open.** The frontend may be on a different domain. Allow all origins at launch; restrict if the API gets abused.

---

## Base URL

```
/api/v1/
```

---

## Endpoints

### `GET /api/v1/bikes`

Main deal feed.

**Query parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `category` | string | — | Filter by category. One of: `Road`, `Mountain`, `Gravel`, `E-Bike`, `Commuter` |
| `city` | string | — | Filter by city (exact match, case-insensitive). e.g. `?city=Seattle` |
| `size` | string (repeatable) | — | Filter by frame_size. Multiple values = OR. e.g. `?size=M&size=L` |
| `vendor` | string | — | Filter by vendor_name (exact match) |
| `min_discount` | int | 0 | Minimum discount_percentage |
| `in_stock` | bool | `true` | Set to `false` to include out-of-stock |
| `q` | string | — | Full-text search on model_name and brand |
| `sort` | string | `discount_desc` | One of: `discount_desc`, `price_asc`, `price_desc` |
| `limit` | int | 50 | Max records per page. Cap at 200 |
| `offset` | int | 0 | Offset for pagination |

**Response:**

```json
{
  "total": 342,
  "limit": 50,
  "offset": 0,
  "results": [
    {
      "id": "a1b2c3d4e5f6a7b8",
      "vendor_name": "Local Bike Shop",
      "brand": "Trek",
      "model_name": "Marlin 5",
      "category": "Mountain",
      "frame_size": "M",
      "price_original": 699.00,
      "price_sale": 499.00,
      "discount_percentage": 29,
      "in_stock": true,
      "product_url": "https://localshop.com/products/trek-marlin-5-m",
      "image_url": "https://cdn.localshop.com/trek-marlin-5.jpg",
      "last_seen_at": "2024-01-15T08:30:00Z"
    }
  ]
}
```

The response envelope (`total`, `limit`, `offset`) is mandatory. Without it, the frontend can't render pagination or a "X deals found" count — the original plan omits this entirely.

**Note on `q` (full-text search):**

- **SQLite:** Use `LIKE '%query%'` on `brand || ' ' || model_name`. Simple, no setup. Slow on large tables but fine for < 50k rows.
- **PostgreSQL:** Use `tsvector` + `GIN` index on `brand || ' ' || model_name`. Fast. Set this up from day one on Postgres — migration from LIKE is straightforward.

Do not implement search as a separate Elasticsearch/Typesense service at this stage. It's premature.

---

### `GET /api/v1/meta/filters`

Returns current distinct values for filter dropdowns. Prevents the UI showing filter options that return zero results.

**Response:**

```json
{
  "categories": ["Gravel", "Mountain", "Road"],
  "cities": ["Denver", "Portland", "Seattle"],
  "sizes": ["L", "M", "S", "XL", "XS"],
  "vendors": ["Bike Gallery", "Local Bike Shop", "Trek Store Seattle"],
  "discount_range": { "min": 5, "max": 60 },
  "total_bikes": 342,
  "last_scraped_at": "2024-01-15T08:30:00Z"
}
```

`last_scraped_at` comes from the most recent `run_at` in `scrape_log` where `status = 'ok'`. This powers the "last updated" banner on the frontend.

Cache this endpoint aggressively (5–60 minutes). It changes only after a scraper run.

---

### `GET /api/v1/health`

Simple liveness check. Returns `{"status": "ok"}`. Used by hosting platform health checks.

---

## Error format

All errors use the same envelope:

```json
{
  "error": {
    "code": "INVALID_PARAM",
    "message": "min_discount must be between 0 and 100",
    "field": "min_discount"
  }
}
```

HTTP status codes:
- `400` — invalid query params
- `404` — not used (all list endpoints return empty arrays, not 404)
- `500` — internal error (scrub the detail before returning to client)

---

## CORS

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to frontend domain in production
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

---

## Caching strategy

The data is stale by design (daily scrapes). Aggressive caching is appropriate.

| Endpoint | Cache-Control |
|---|---|
| `/api/v1/bikes` | `max-age=3600` (1 hour) |
| `/api/v1/meta/filters` | `max-age=3600` (1 hour) |
| `/api/v1/health` | `no-cache` |

A CDN (Cloudflare free tier) in front of the API will absorb most traffic without hitting the server at all.

---

## What the original plan is missing

1. **Pagination** — critical; `GET /bikes` with no limit returns all records.
2. **Response envelope** — without `total`, the frontend can't show "342 deals found" or page controls.
3. **`in_stock` filter** — users want to see active deals only by default.
4. **`sort` parameter** — discount is the default but price-sort is a reasonable secondary option.
5. **Health endpoint** — required by every hosting platform for zero-downtime deploys.
6. **Error format** — undefined in the original plan.
7. **CORS** — not mentioned; the frontend will hit CORS errors on day one without this.
