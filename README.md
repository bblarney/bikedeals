# BikeGrid

Aggregates discounted bike listings from local Australian bike shops into a single searchable feed.

Daily scrapers pull inventory from 77 shop websites, normalise it into a common schema, and store it in a database. A FastAPI layer serves the data to a React frontend filtered by city, category, size, brand, price, and discount.

```
[Shop Websites] → [Scrapers / GitHub Actions] → [Supabase DB]
        ↑                                             ↓
[Cloudflare Worker]     [Cloudflare Pages] ← [FastAPI / Render]
   (CI egress)
```

## Stack

| Layer | Tech |
|---|---|
| Scraper | Python · httpx · BeautifulSoup4 · Pydantic |
| Database | Supabase (PostgreSQL) · SQLAlchemy · Alembic |
| API | FastAPI · uvicorn |
| Frontend | React · Vite · Tailwind CSS · TanStack Query |
| Infra | GitHub Actions (cron) · Render (API) · Cloudflare Pages (frontend) · Cloudflare Workers (scraper egress) |

## Development

```bash
pip install -r requirements-dev.txt   # includes requirements.txt
pytest                                  # full suite
python -m scrapers.scrape_check "Crooze"  # test one vendor, no DB writes
uvicorn api.main:app --reload           # API on :8000
cd frontend && npm install && npm run dev
```

Without `DATABASE_URL` the scraper skips all database writes, so `scrape_check` and a bare `python -m scrapers.run` are safe locally.

## Docs

Start with [`docs/scraper-design.md`](docs/scraper-design.md) if you're adding a shop — there's a required checklist, and a step that's easy to miss (the egress proxy allowlist).

| Doc | Covers |
|---|---|
| [`architecture.md`](docs/architecture.md) | Topology, hosting, ORM and migration mandate |
| [`data-model.md`](docs/data-model.md) | Tables, DDL, ID strategy, variants |
| [`scraper-design.md`](docs/scraper-design.md) | New-vendor checklist, the seven pipelines, quarantine |
| [`api-design.md`](docs/api-design.md) | Endpoints, rate limits, CORS, caching |
| [`frontend.md`](docs/frontend.md) | Routes, components, state |
| [`developer.md`](docs/developer.md) | PR conventions, coding guidelines |
| [`vendors.md`](docs/vendors.md) | Coverage tracker — scraped, blocked, and why |
| [`worker/README.md`](worker/README.md) | Scraper egress proxy and its allowlist |
