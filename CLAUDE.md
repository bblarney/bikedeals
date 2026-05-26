# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Bikedeals** is a deal-aggregation site for local bike shops. Daily scrapers ingest shop inventories into a normalized database; a FastAPI layer serves the data; a Vue 3/React SPA presents it.

```
[Shop Web Nodes] ──> (Daily Cron: Async Scrapers) ──> [Normalized Database]
                                                               │
[Client Browser] <── (Static Web Frontend) <── [FastAPI Layer] ┘
```

## Tech Stack

| Layer | Tech |
|---|---|
| Scrapers | Python, `httpx` (async), `beautifulsoup4`, `pydantic` |
| Database | SQLite (dev) → PostgreSQL (prod) |
| API | FastAPI + uvicorn |
| Frontend | React + Vite + Tailwind CSS + TanStack Query |
| Hosting | GitHub Actions (scraper cron) · Supabase (DB) · Render/Railway (API) · Cloudflare Pages (frontend) |

## Architecture

### Ingestion (two pipelines)

- **Pipeline A — Modern e-commerce (Shopify/BigCommerce):** fetch `/products.json?limit=250` from the store domain. Returns structured fields; no DOM parsing needed.
- **Pipeline B — Legacy/custom sites (WooCommerce/custom HTML):** DOM-targeted micro-scrapers keyed to retailer CSS selectors. A failing sub-scraper must log an alert and be quarantined — never corrupt the database.

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
  "last_updated": "ISO 8601 timestamp"
}
```

### API endpoints

- `GET /api/v1/bikes` — main feed; query params: `category`, `size`, `vendor`, `min_discount`, `search_query`; default sort: `discount_percentage` desc
- `GET /api/v1/meta/filters` — returns dropdown options (sizes, brands, shops)

### Database indexes

Multi-column indexes on `category`, `frame_size`, `vendor_name`, and `discount_percentage` (desc) for sub-second filtering.

## Design documents

Detailed planning and critique for each layer — read these before touching that layer's code:

- [`docs/architecture.md`](docs/architecture.md) — deployment options, ORM mandate, geographic scope question
- [`docs/data-model.md`](docs/data-model.md) — full DDL, ID strategy, variant handling, timestamps, category normalization
- [`docs/scraper-design.md`](docs/scraper-design.md) — pipeline A/B detail, rate limiting, UPSERT logic, quarantine, alerting
- [`docs/api-design.md`](docs/api-design.md) — full endpoint spec, pagination, CORS, error format
- [`docs/frontend.md`](docs/frontend.md) — framework decision, component tree, state management, UX choices
- [`docs/developer.md`](docs/developer.md) — PR conventions and coding guidelines

## Build Roadmap (Phase order matters)

1. **Phase 1** — Two scrapers (Shopify + WooCommerce), export to local JSON, validate normalization.
2. **Phase 2** — Load JSON into local SQLite DB, stand up FastAPI service.
3. **Phase 3** — Build frontend with dummy cards, iterate layout, then connect to real API.
