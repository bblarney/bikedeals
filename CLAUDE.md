# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Bikedeals** is a deal-aggregation site for Australian local bike shops. Daily scrapers ingest shop inventories from 77 vendors into a normalized database; a FastAPI layer serves the data; a React SPA presents it.

```
[Shop Web Nodes] <── (Cloudflare Worker proxy, CI only)
       │
       └──> (Daily Cron: Async Scrapers) ──> [Normalized Database]
                                                       │
[Client Browser] <── (Static Web Frontend) <── [FastAPI Layer] ┘
```

**Adding a vendor requires a Worker redeploy.** CI egress runs through a
Cloudflare Worker that enforces a vendor-hostname allowlist; a new shop must be
added to `ALLOWED_HOSTS` in `worker/worker.js` and the Worker redeployed, or it
403s nightly while every other vendor succeeds. Full checklist in
[`docs/scraper-design.md`](docs/scraper-design.md).

## Tech Stack

| Layer | Tech |
|---|---|
| Scrapers | Python, `httpx` (async), `beautifulsoup4`, `pydantic` |
| Database | SQLite (dev) → PostgreSQL (prod) |
| API | FastAPI + uvicorn |
| Frontend | React + Vite + Tailwind CSS + TanStack Query |
| Hosting | GitHub Actions (scraper cron) · Supabase (DB) · Render/Railway (API) · Cloudflare Pages (frontend) |

## Architecture

### Ingestion (six pipelines)

Selected per vendor via `pipeline:` in the YAML; dispatch in `scrapers/orchestrator.py`.

- **JSON feeds:** `shopify` (`/products.json` or `/collections/<handle>/products.json`), `woocommerce_api` (WooCommerce Store API at `/wp-json/wc/store/v1`).
- **DOM scrapers:** `woocommerce`, `bigcommerce`, `giant`, `canyon` — keyed to retailer CSS selectors, and expected to break when shops redesign.

A failing vendor is quarantined for that run: nothing is written, yesterday's data is kept, and the run continues. Never corrupt the database.

### Normalized bike schema (every scraper must produce this)

```json
{
  "id": "string",
  "vendor_name": "string",
  "city": "string",
  "brand": "string",
  "model_name": "string",
  "category": "Road|Mountain|Gravel|E-Bike|Commuter",
  "frame_size": "string",
  "price_original": 0.0,
  "price_sale": 0.0,
  "discount_percentage": 0,
  "in_stock": true,
  "product_url": "string",
  "image_url": "string",
  "scraped_at": "ISO 8601 timestamp",
  "last_seen_at": "ISO 8601 timestamp"
}
```

Optional enrichment fields where the shop publishes them: `sku` (the shop's own,
not globally unique — `product_key` is the cross-shop matching key), `weight_grams`, `product_updated_at`, `tags`, `frame_material`,
`drivetrain_groupset`. `city` is nullable. See
[`docs/data-model.md`](docs/data-model.md) for the authoritative definition.

### API endpoints

- `GET /api/v1/bikes` — main feed; most filters are repeatable and OR together (`category`, `city`, `size`, `vendor`, `brand`, `frame_material`, `drivetrain_groupset`), plus `min_discount`, `min_price`/`max_price`, `in_stock`, `q`, `added_since`, `product_key`, `sort`, `limit`/`offset`. Default sort `discount_desc`.
- `GET /api/v1/bikes/{id}` — detail, with cross-shop offers for the same SKU and other size variants
- `GET /api/v1/bikes/{id}/price-history` · `POST /api/v1/bikes/{id}/click`
- `GET /api/v1/meta/filters` — faceted dropdown options (each facet excludes itself)
- `GET /api/v1/meta/stats` · `GET /api/v1/health` · `GET /sitemap.xml`
- `POST /api/v1/subscribe` · `POST /api/v1/unsubscribe`

Full spec in [`docs/api-design.md`](docs/api-design.md).

### Database indexes

Single-column indexes on the filterable fields, plus two composites for the common feed queries: `(category, frame_size, vendor_name)` and `(in_stock, discount_percentage)`.

### Migrations

Alembic owns the Postgres schema (`alembic upgrade head`). `Base.metadata.create_all` is guarded to SQLite in both `api/main.py` and `scrapers/run.py` — running it on Postgres creates tables outside Alembic's tracking and breaks the next migration.

## Design documents

Detailed planning and critique for each layer — read these before touching that layer's code:

- [`docs/architecture.md`](docs/architecture.md) — topology, hosting, ORM/migration mandate, geographic scope
- [`docs/data-model.md`](docs/data-model.md) — all four tables, DDL, ID strategy, variants, timestamps
- [`docs/scraper-design.md`](docs/scraper-design.md) — **new-vendor checklist**, the six pipelines, rate limiting, egress proxy, quarantine, UPSERT
- [`docs/api-design.md`](docs/api-design.md) — full endpoint spec, rate limits, CORS, error formats, caching
- [`docs/frontend.md`](docs/frontend.md) — routes, component tree, state management, UX choices
- [`docs/developer.md`](docs/developer.md) — PR conventions, vendor testing, coding guidelines
- [`docs/vendors.md`](docs/vendors.md) — coverage tracker: scraped, blocked, and why
- [`docs/implementation-plan.md`](docs/implementation-plan.md) — **historical**; the original build guide, superseded by the docs above
- [`worker/README.md`](worker/README.md) — the egress proxy, its allowlist, and deployment

## Status

Phases 1–4 are complete: 77 vendors scraping daily into Supabase, the API on
Render, the frontend on Cloudflare Pages. Work now is incremental — new vendors,
pipeline fixes, and frontend iteration.
