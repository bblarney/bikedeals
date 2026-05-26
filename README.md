# Bikedeals

Aggregates discounted bike listings from local Australian bike shops into a single searchable feed.

Daily scrapers pull inventory from shop websites, normalise it into a common schema, and store it in a database. A FastAPI layer serves the data to a React frontend filtered by city, category, size, and discount.

```
[Shop Websites] → [Scrapers / GitHub Actions] → [Supabase DB]
                                                      ↓
                        [Cloudflare Pages] ← [FastAPI / Render]
```

## Stack

| Layer | Tech |
|---|---|
| Scraper | Python · httpx · BeautifulSoup4 · Pydantic |
| Database | Supabase (PostgreSQL) · SQLAlchemy |
| API | FastAPI · uvicorn |
| Frontend | React · Vite · Tailwind CSS · TanStack Query |
| Infra | GitHub Actions (cron) · Render (API) · Cloudflare Pages (frontend) |

## Docs

Architecture, data model, API design, and scraper design are in [`docs/`](docs/).
