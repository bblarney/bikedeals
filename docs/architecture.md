# Architecture

## System topology

```
[Shop Web Nodes]
      ▲
      │ (CI only: egress via Cloudflare Worker proxy — worker/README.md)
      │
[Async Scrapers]  ── scrape_log ──> [summary email, every run]
      │
      ▼ (UPSERT daily, 08:00 UTC)
[PostgreSQL — Supabase]
      │
      ▼
[FastAPI / uvicorn — Render]
      │
      ▼
[Static SPA — Cloudflare Pages] ──> [User browser]
```

The SPA is truly static (pre-built HTML/JS/CSS). The FastAPI layer is the only
runtime process that must stay up.

**The Worker proxy is load-bearing in CI.** GitHub Actions' datacenter IP range is
blocked as a class by Cloudflare and Shopify, so vendor requests are re-issued from
Cloudflare's network. It enforces a vendor-hostname allowlist, which must be
updated *and redeployed* whenever a vendor is added — see the checklist in
`scraper-design.md`. Locally the proxy is inert.

---

## Deployment options

The original plan lists "AWS Lambda / Cloud Run / GitHub Actions" as if they are equivalent. They are not. Pick one path early.

### Option A — GitHub Actions + free managed services (recommended for early stage)

| Component | Service | Cost |
|---|---|---|
| Scraper cron | GitHub Actions (free 2000 min/month) | $0 |
| Database | Supabase free tier (PostgreSQL, 500 MB) | $0 |
| API | Railway or Render free tier | $0 |
| Frontend | Cloudflare Pages or Vercel | $0 |

**Tradeoff:** Supabase free tier sleeps after inactivity. Render's free tier also spins down. Acceptable for a side project; unacceptable if sub-second cold starts matter.

### Option B — AWS Lambda + RDS

More ops overhead and cost (RDS has no free tier after 12 months), but fits neatly into the AWS ecosystem and scales to production without migration.

### Option C — Single VPS (e.g. $6/mo Hetzner CX11)

Run Postgres, FastAPI, and a cron job on one machine. Zero cold starts, zero platform lock-in, full control. Simplest operationally once you've outgrown free tiers.

**Decision: Option A**, and this is what runs today — GitHub Actions (daily scrape),
Supabase (Postgres), Render (API), Cloudflare Pages (frontend), plus a free
Cloudflare Worker for scraper egress. Total cost still $0.

---

## Settled decisions

All resolved and implemented. See each specialist doc for detail.

| Decision | Outcome | Doc |
|---|---|---|
| Frontend framework | **React 19 + Vite + Tailwind 4 + TanStack Query** | `frontend.md` |
| Geographic scope | **Australia only, multi-city** | this doc |
| Multi-variant products (one row per size?) | **One row per size** | `data-model.md` |
| Hosting | **GHA + Supabase + Render + CF Pages** | this doc |
| ID / deduplication strategy | **Hash of `vendor_name::city::product_url::frame_size`** | `data-model.md` |
| ORM vs raw SQL | **SQLAlchemy** | `data-model.md` |
| Schema migrations | **Alembic owns Postgres; `create_all` is SQLite-only** | `data-model.md` |
| Pagination strategy | **Offset pagination** | `api-design.md` |
| Category normalization | Per-vendor map in the vendor registry | `scraper-design.md` |
| CI egress | **Cloudflare Worker proxy with a host allowlist** | `worker/README.md` |
| Alerting destination | Summary email after every run (not just failures) | `scraper-design.md` |

The ID strategy gained `city` and `frame_size` after launch: `frame_size` because
one row per size variant means sizes must not collide, and `city` because a
national chain fans one product out to one row per city.

---

## Geographic scope

**Decision: Australia only at launch, multi-city within Australia.** A `city` field is denormalized onto every bike row and set via the vendor registry config. The API exposes a `city` filter param and the frontend has a city dropdown. No country field is needed — all vendors are Australian.

Cities in scope are the major Australian metros: Sydney, Melbourne, Brisbane, Perth, Adelaide, and others as vendor coverage grows. If intra-city filtering becomes too coarse (e.g. multiple distinct shop clusters in Sydney), a `state` field (NSW, VIC, QLD, etc.) can be added later without breaking the schema.

Prices are in AUD. See `data-model.md`.

---

## ORM mandate

SQLite for dev, PostgreSQL for prod. That split is painful without an ORM because
the dialects are incompatible (`AUTOINCREMENT` vs `SERIAL`, `STRFTIME` vs
`date_trunc`). **SQLAlchemy** carries one set of model definitions against both
backends. This is a non-negotiable architectural guard rail.

`api/models.py` is the single source of truth; both the API and the scraper import
from it. **Alembic** owns the Postgres schema — `Base.metadata.create_all` is
guarded to SQLite in both entry points, because running it on Postgres creates
tables outside Alembic's tracking and breaks the next migration.
