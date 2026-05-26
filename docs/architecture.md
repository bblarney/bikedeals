# Architecture

## System topology

```
[Shop Web Nodes]
      │
      ▼
[Async Scrapers] ── quarantine log ──> [Alert channel]
      │
      ▼ (UPSERT daily)
[Database]
      │
      ▼
[FastAPI / uvicorn]
      │
      ▼
[Static SPA] ──> [User browser]
```

The SPA is truly static (pre-built HTML/JS/CSS). The FastAPI layer is the only runtime process that must stay up.

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

**Decision: Option A.** GitHub Actions + Supabase + Render/Railway + Cloudflare Pages.

---

## Critical unresolved decisions

These must be answered before writing code. See each specialist doc for detail.

| Decision | Status | Doc |
|---|---|---|
| Frontend framework | **React** | `frontend.md` |
| Geographic scope | **Multi-city from day one** | `data-model.md` |
| Multi-variant products (one row per size?) | **One row per size** | `data-model.md` |
| Hosting | **Free managed services (GHA + Supabase + Render + CF Pages)** | this doc |
| ID / deduplication strategy | **Hash of vendor_name::product_url** | `data-model.md` |
| ORM vs raw SQL | **SQLAlchemy** | `data-model.md` |
| Pagination strategy | **Offset pagination** | `api-design.md` |
| Category normalization | Per-vendor map in vendor registry | `scraper-design.md` |
| Alerting destination | GHA job failure (email) + optional Slack webhook | `scraper-design.md` |

---

## Geographic scope

**Decision: Australia only at launch, multi-city within Australia.** A `city` field is denormalized onto every bike row and set via the vendor registry config. The API exposes a `city` filter param and the frontend has a city dropdown. No country field is needed — all vendors are Australian.

Cities in scope are the major Australian metros: Sydney, Melbourne, Brisbane, Perth, Adelaide, and others as vendor coverage grows. If intra-city filtering becomes too coarse (e.g. multiple distinct shop clusters in Sydney), a `state` field (NSW, VIC, QLD, etc.) can be added later without breaking the schema.

Prices are in AUD. See `data-model.md`.

---

## ORM mandate

The plan says SQLite for dev, PostgreSQL for prod. This migration is painful without an ORM because SQLite and PostgreSQL have incompatible SQL dialects (e.g. `AUTOINCREMENT` vs `SERIAL`, `STRFTIME` vs `date_trunc`). Use **SQLAlchemy** (Core or ORM) from day one with the same model definitions targeting both backends. This is a non-negotiable architectural guard rail.
