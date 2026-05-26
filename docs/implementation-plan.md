# Implementation Plan

This document is the authoritative step-by-step build guide for Bikedeals. All design decisions referenced here are already resolved — do not re-litigate them. Read each section fully before writing any code for it, and read the linked design doc before touching that layer.

---

## Resolved decisions (do not re-open)

| Question | Answer |
|---|---|
| Frontend framework | React + Vite + Tailwind CSS + TanStack Query |
| ORM | SQLAlchemy — PostgreSQL everywhere (Supabase for both dev and prod) |
| DB ID strategy | `sha256(vendor_name::product_url::frame_size)[:16]` |
| Variants | One row per size variant |
| Pagination | Offset pagination |
| Hosting | GitHub Actions + Supabase + Render/Railway + Cloudflare Pages |
| Geographic scope | Australian cities only; `city` field on every bike row |
| Alerting | GitHub Actions job failure (emails owner); optional Slack webhook later |
| `discount_percentage` | Computed in scraper, stored as column, always recomputed on UPSERT |
| Image URL breakage | Accept 404 breakage; show placeholder. No re-hosting yet. |
| Category fallback | If no tag matches `category_map`, log and skip the record. Do not guess. |
| Full-text search | `LIKE '%q%'` on `brand \|\| ' ' \|\| model_name` — fast enough at < 50k rows, no setup required |
| Stale product handling | Mark `in_stock = 0` after `last_seen_at < run_start_time`; never delete rows |

---

## Repo layout (create this structure before writing any code)

```
bikedeals/
├── scrapers/
│   ├── vendors/                  # YAML vendor configs, one file per shop
│   ├── pipelines/
│   │   ├── __init__.py
│   │   ├── shopify.py            # Pipeline A
│   │   └── woocommerce.py        # Pipeline B
│   ├── models.py                 # Pydantic: BikeRecord, VendorConfig, ScrapeResult
│   ├── db.py                     # UPSERT + stale-mark logic (SQLAlchemy)
│   ├── orchestrator.py           # Async run loop, quarantine, scrape_log writes
│   └── run.py                    # Entry point: python -m scrapers.run
├── api/
│   ├── main.py                   # FastAPI app, CORS, all route handlers
│   ├── db.py                     # SQLAlchemy engine + session dependency
│   ├── models.py                 # SQLAlchemy ORM table definitions (shared with scrapers)
│   └── schemas.py                # Pydantic response models
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── api/
│   │   │   └── client.js         # fetch wrappers for /bikes and /meta/filters
│   │   ├── hooks/
│   │   │   └── useFilters.js     # read/write URL search params
│   │   └── components/
│   │       ├── Header.jsx
│   │       ├── StatsBanner.jsx
│   │       ├── FilterStrip.jsx
│   │       ├── BikeCard.jsx
│   │       ├── BikeGrid.jsx
│   │       ├── Pagination.jsx
│   │       └── states/
│   │           ├── LoadingState.jsx
│   │           ├── ErrorState.jsx
│   │           └── EmptyState.jsx
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── docs/                         # Design docs (already present)
├── .github/
│   └── workflows/
│       └── scraper.yml           # Daily cron job
├── requirements.txt              # Python deps
└── .env.example                  # DATABASE_URL, VITE_API_BASE_URL, etc.
```

The `api/models.py` file defines the SQLAlchemy ORM classes. Both the scraper (`scrapers/db.py`) and the API (`api/db.py`) import from `api/models.py`. Do not duplicate the table definitions.

---

## Phase 1 — Scrapers → Local JSON

**Goal:** Two working scrapers that produce validated `BikeRecord` JSON. No database writes yet.

Read `docs/scraper-design.md` and `docs/data-model.md` before starting this phase.

---

### Task 1.1 — Python project setup

Create `requirements.txt`:

```
httpx[asyncio]>=0.27
beautifulsoup4>=4.12
pydantic>=2.7
sqlalchemy>=2.0
asyncpg>=0.29
pyyaml>=6.0
python-dotenv>=1.0
```

Create `.env.example`:

```
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/postgres
```

No `.env` file should ever be committed. Add `.env` to `.gitignore`.

**Done when:** `pip install -r requirements.txt` succeeds with no errors.

---

### Task 1.2 — Shared Pydantic models (`scrapers/models.py`)

Define three models in this file:

**`VendorConfig`** — represents one entry in the vendor registry YAML:

```python
class VendorConfig(BaseModel):
    vendor_name: str
    city: str
    base_url: str
    pipeline: Literal["shopify", "woocommerce", "custom"]
    category_map: dict[str, str]   # lowercase shop tag → our category
    selectors: dict[str, str] | None = None   # Pipeline B only
```

**`BikeRecord`** — the normalized output every scraper must produce:

```python
class BikeRecord(BaseModel):
    id: str                           # sha256(vendor_name::product_url::frame_size)[:16]
    vendor_name: str
    city: str
    brand: str
    model_name: str
    category: Literal["Road", "Mountain", "Gravel", "E-Bike", "Commuter"]
    frame_size: str
    price_original: float | None
    price_sale: float
    discount_percentage: int          # always recompute: round((1 - sale/original) * 100)
    in_stock: bool
    product_url: str
    image_url: str | None
    scraped_at: datetime
    last_seen_at: datetime

    @model_validator(mode="after")
    def check_prices(self) -> "BikeRecord":
        if self.price_original is not None and self.price_sale > self.price_original:
            raise ValueError(f"price_sale ({self.price_sale}) > price_original ({self.price_original})")
        return self
```

**`ScrapeResult`** — what each scraper returns:

```python
class ScrapeResult(BaseModel):
    vendor_name: str
    bikes: list[BikeRecord]
    error: str | None = None
```

Also define the ID generation helper in this file:

```python
import hashlib

def make_bike_id(vendor_name: str, product_url: str, frame_size: str) -> str:
    key = f"{vendor_name}::{product_url}::{frame_size}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

And the discount computation helper:

```python
def compute_discount(price_sale: float, price_original: float | None) -> int:
    if not price_original or price_original <= 0:
        return 0
    if price_sale >= price_original:
        return 0
    return round((1 - price_sale / price_original) * 100)
```

**Done when:** `from scrapers.models import BikeRecord, VendorConfig, ScrapeResult` imports cleanly.

---

### Task 1.3 — Vendor registry loader

Create `scrapers/vendors/` directory. Each file is a YAML with one vendor's config.

Create two example vendor files for testing. Use real Australian bike shops on Shopify and WooCommerce. Look for shops that have `/products.json` accessible (Shopify) or visible WooCommerce product markup.

Example structure for `scrapers/vendors/example-shopify.yaml`:

```yaml
vendor_name: "Example Bikes Sydney"
city: "Sydney"
base_url: "https://example-shop.com.au"
pipeline: "shopify"
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

Create `scrapers/registry.py` with a loader:

```python
import yaml
from pathlib import Path
from scrapers.models import VendorConfig

VENDORS_DIR = Path(__file__).parent / "vendors"

def load_registry() -> list[VendorConfig]:
    configs = []
    for path in VENDORS_DIR.glob("*.yaml"):
        with path.open() as f:
            data = yaml.safe_load(f)
        configs.append(VendorConfig(**data))
    return configs
```

**Done when:** `load_registry()` returns a list of `VendorConfig` objects with no validation errors.

---

### Task 1.4 — Pipeline A: Shopify (`scrapers/pipelines/shopify.py`)

Read `docs/scraper-design.md § Pipeline A` before implementing.

The scraper must:

1. Check `robots.txt` for the domain before making any product requests. If `/products.json` or `/*` is disallowed, log a warning and return an empty `ScrapeResult`.
2. Paginate `GET {base_url}/products.json?limit=250&page={n}` until the response returns fewer than 250 products.
3. Set `User-Agent: BikeDeals-Scraper/1.0 (+https://bikedeals.example.com)` on every request.
4. Add `await asyncio.sleep(random.uniform(1.0, 2.0))` between page requests.
5. For each product, iterate `variants[]` and emit one `BikeRecord` per variant. Skip variants whose `title` is `"Default Title"` or contains colour keywords rather than sizes (e.g. "Black", "Red", "Blue") — these are not size variants.
6. Map fields per `docs/scraper-design.md § Field mapping`.
7. Resolve `category` via `config.category_map`. Match against lowercase product type and all tags. If no match, log the product handle and skip it (do not emit a `BikeRecord` for it).
8. Build `product_url` from `{base_url}/products/{handle}?variant={variant_id}`.
9. Compute `id` using `make_bike_id(vendor_name, product_url, frame_size)`.
10. Compute `discount_percentage` using `compute_discount()`.
11. Set `scraped_at = last_seen_at = datetime.utcnow()`.
12. Validate each `BikeRecord` through Pydantic before adding to results. On validation error, log and skip the record — never raise.

Function signature:

```python
async def scrape_shopify(config: VendorConfig, client: httpx.AsyncClient) -> list[BikeRecord]:
    ...
```

**Done when:** Running against a real Shopify bike shop returns a non-empty list of valid `BikeRecord` objects that print cleanly as JSON.

---

### Task 1.5 — Pipeline B: WooCommerce (`scrapers/pipelines/woocommerce.py`)

Read `docs/scraper-design.md § Pipeline B` before implementing.

The scraper must:

1. Same `robots.txt` check, `User-Agent`, and rate limiting as Pipeline A.
2. Fetch the product listing page(s) using selectors from `config.selectors`.
3. For each product element matched by `selectors["product_list"]`, extract:
   - `model_name` via `selectors["model_name"]`
   - `price_sale` via `selectors["price_sale"]` — parse the string to float, strip `$` and commas
   - `price_original` via `selectors["price_original"]` — optional; None if absent
   - `product_url` via `selectors["product_url"]` — may be relative; resolve to absolute
   - `image_url` via `selectors["image_url"]`
   - `frame_size` via `selectors["frame_size"]` — optional; use `"One Size"` if absent
4. `brand` is not reliably in the product list for WooCommerce. Use `config.vendor_name` as the brand fallback, or scrape the individual product page if a `selectors["brand"]` key exists.
5. Apply the same category resolution, `make_bike_id`, `compute_discount`, and Pydantic validation as Pipeline A.

Function signature:

```python
async def scrape_woocommerce(config: VendorConfig, client: httpx.AsyncClient) -> list[BikeRecord]:
    ...
```

**Done when:** Running against a real WooCommerce bike shop returns valid `BikeRecord` objects.

---

### Task 1.6 — Orchestrator (`scrapers/orchestrator.py`)

```python
MAX_CONCURRENT_VENDORS = 5

async def run_all(vendors: list[VendorConfig]) -> list[ScrapeResult]:
    sem = asyncio.Semaphore(MAX_CONCURRENT_VENDORS)
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [scrape_vendor(v, client, sem) for v in vendors]
        return await asyncio.gather(*tasks)

async def scrape_vendor(config: VendorConfig, client: httpx.AsyncClient, sem: asyncio.Semaphore) -> ScrapeResult:
    async with sem:
        try:
            if config.pipeline == "shopify":
                bikes = await scrape_shopify(config, client)
            elif config.pipeline == "woocommerce":
                bikes = await scrape_woocommerce(config, client)
            else:
                raise NotImplementedError(f"Pipeline {config.pipeline!r} not implemented")
            return ScrapeResult(vendor_name=config.vendor_name, bikes=bikes)
        except Exception as e:
            logging.error(f"[{config.vendor_name}] scrape failed: {e}", exc_info=True)
            return ScrapeResult(vendor_name=config.vendor_name, bikes=[], error=str(e))
```

A quarantined result must never write bike records to the database. The orchestrator must write a `scrape_log` entry for every vendor regardless of success or failure.

**Done when:** Running the orchestrator against both test vendors produces `ScrapeResult` objects with non-empty `bikes` lists, no unhandled exceptions, and a scrape_log entry for each vendor.

---

### Task 1.7 — Entry point and JSON export (`scrapers/run.py`)

```python
if __name__ == "__main__":
    vendors = load_registry()
    results = asyncio.run(run_all(vendors))
    # Phase 1: write to JSON for inspection
    output = [r.model_dump(mode="json") for r in results if r.error is None]
    Path("output.json").write_text(json.dumps(output, indent=2))
```

**Phase 1 is done when:**
- `python -m scrapers.run` completes without crashing.
- `output.json` contains valid bike records for both vendors.
- Every `BikeRecord` in the output has all required fields populated.
- Category values are only from the allowed enum.
- No `price_sale > price_original` records appear in output.

---

## Phase 2 — Database + FastAPI

**Goal:** Scraper writes to PostgreSQL (Supabase); FastAPI serves the data. End-to-end curl test passes.

Read `docs/data-model.md`, `docs/scraper-design.md § UPSERT`, and `docs/api-design.md` before starting.

---

### Task 2.1 — SQLAlchemy models (`api/models.py`)

These are the canonical ORM table definitions. Both the scraper and the API import from here.

```python
from sqlalchemy import Column, Text, Float, Integer, Boolean, DateTime, CheckConstraint, Index
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Bike(Base):
    __tablename__ = "bikes"
    id = Column(Text, primary_key=True)
    vendor_name = Column(Text, nullable=False)
    city = Column(Text, nullable=False)
    brand = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    frame_size = Column(Text, nullable=False)
    price_original = Column(Float, nullable=True)
    price_sale = Column(Float, nullable=False)
    discount_percentage = Column(Integer, nullable=False, default=0)
    in_stock = Column(Boolean, nullable=False, default=True)
    product_url = Column(Text, nullable=False, unique=True)
    image_url = Column(Text, nullable=True)
    scraped_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("category IN ('Road','Mountain','Gravel','E-Bike','Commuter')", name="chk_category"),
        CheckConstraint("price_sale > 0", name="chk_price"),
        CheckConstraint("discount_percentage >= 0 AND discount_percentage <= 100", name="chk_discount"),
        Index("idx_bikes_category", "category"),
        Index("idx_bikes_frame_size", "frame_size"),
        Index("idx_bikes_vendor", "vendor_name"),
        Index("idx_bikes_city", "city"),
        Index("idx_bikes_discount_desc", "discount_percentage"),
        Index("idx_bikes_in_stock", "in_stock"),
    )

class ScrapeLog(Base):
    __tablename__ = "scrape_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vendor_name = Column(Text, nullable=False)
    run_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Text, nullable=False)    # 'ok' | 'quarantined' | 'skipped'
    error_msg = Column(Text, nullable=True)
    bikes_upserted = Column(Integer, default=0)
```

`Base.metadata.create_all` handles both tables and all indexes. No separate SQL file needed.

---

### Task 2.2 — DB session and UPSERT (`scrapers/db.py`)

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from api.models import Bike, ScrapeLog, Base

async def get_engine(url: str):
    return create_async_engine(url)

async def init_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def upsert_bikes(session: AsyncSession, records: list[BikeRecord]):
    for r in records:
        stmt = pg_insert(Bike).values(**r.model_dump()).on_conflict_do_update(
            index_elements=["id"],
            set_={
                "price_sale": r.price_sale,
                "price_original": r.price_original,
                "discount_percentage": r.discount_percentage,
                "in_stock": r.in_stock,
                "last_seen_at": r.last_seen_at,
            }
        )
        await session.execute(stmt)
    await session.commit()

async def mark_stale(session: AsyncSession, vendor_name: str, run_start: datetime):
    await session.execute(
        update(Bike)
        .where(Bike.vendor_name == vendor_name, Bike.last_seen_at < run_start)
        .values(in_stock=False)
    )
    await session.commit()
```

**Done when:** `upsert_bikes` writes records to Supabase and re-running it updates existing rows without creating duplicates (verify with `SELECT COUNT(*) FROM bikes` in the Supabase SQL editor).

---

### Task 2.3 — FastAPI app scaffold (`api/main.py`)

All route handlers live directly in `main.py`. No `routers/` subdirectory.

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Bikedeals API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}

# /api/v1/bikes and /api/v1/meta/filters are defined in the same file — see Task 2.5
```

`api/db.py` — database session dependency:

```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(os.environ["DATABASE_URL"])  # must be set; no default
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with SessionLocal() as session:
        yield session
```

---

### Task 2.4 — Response schemas (`api/schemas.py`)

```python
from pydantic import BaseModel
from datetime import datetime

class BikeResponse(BaseModel):
    id: str
    vendor_name: str
    city: str
    brand: str
    model_name: str
    category: str
    frame_size: str
    price_original: float | None
    price_sale: float
    discount_percentage: int
    in_stock: bool
    product_url: str
    image_url: str | None
    last_seen_at: datetime

    class Config:
        from_attributes = True

class PaginatedBikes(BaseModel):
    total: int
    limit: int
    offset: int
    results: list[BikeResponse]

class FiltersResponse(BaseModel):
    categories: list[str]
    cities: list[str]
    sizes: list[str]
    vendors: list[str]
    discount_range: dict     # {"min": int, "max": int}
    total_bikes: int
    last_scraped_at: datetime | None
```

---

### Task 2.5 — Route handlers (in `api/main.py`)

Implement `GET /api/v1/bikes` with these query params (all optional):

| Param | Type | Default | Behaviour |
|---|---|---|---|
| `category` | str | — | `WHERE category = :category` |
| `city` | str | — | `WHERE LOWER(city) = LOWER(:city)` |
| `size` | list[str] | — | `WHERE frame_size IN (:sizes)` |
| `vendor` | str | — | `WHERE vendor_name = :vendor` |
| `min_discount` | int | 0 | `WHERE discount_percentage >= :min_discount` |
| `in_stock` | bool | True | `WHERE in_stock = True` (omit filter if False) |
| `q` | str | — | `WHERE (brand \|\| ' ' \|\| model_name) ILIKE '%' \|\| :q \|\| '%'` |
| `sort` | str | `discount_desc` | `ORDER BY discount_percentage DESC` or `price_asc`/`price_desc` |
| `limit` | int | 50 | Cap at 200 |
| `offset` | int | 0 | — |

Build the query incrementally by appending `.where()` clauses on a base `select(Bike)` statement. Use SQLAlchemy Core expressions, not raw strings.

Run two queries: one `COUNT(*)` for `total`, one paginated for `results`. Return a `PaginatedBikes`.

Set `Cache-Control: max-age=3600` on the response.

Implement `GET /api/v1/meta/filters`:

Run distinct queries for categories, cities, sizes, vendors. Use `func.min()` / `func.max()` for discount range. Fetch `last_scraped_at` from `SELECT MAX(run_at) FROM scrape_log WHERE status = 'ok'`.

Set `Cache-Control: max-age=3600`.

**Done when:**

```bash
curl "http://localhost:8000/api/v1/bikes?limit=5" | python -m json.tool
curl "http://localhost:8000/api/v1/meta/filters" | python -m json.tool
```

Both return valid JSON matching the schemas in `docs/api-design.md`.

---

### Task 2.6 — End-to-end Phase 2 test

Set `DATABASE_URL` in a local `.env` file pointing to your Supabase project connection string before running.

1. `python -m scrapers.run` — writes to Supabase; confirm row count in Supabase SQL editor
2. `uvicorn api.main:app --reload`
3. `curl http://localhost:8000/api/v1/health` → `{"status": "ok"}`
4. `curl "http://localhost:8000/api/v1/bikes?limit=3"` → paginated results
5. `curl "http://localhost:8000/api/v1/meta/filters"` → filter options
6. `curl "http://localhost:8000/api/v1/bikes?category=Road&min_discount=10"` → filtered results
7. `curl "http://localhost:8000/api/v1/bikes?q=trek"` → search results

**Phase 2 is done when** all six curls return valid, non-empty responses and a second `python -m scrapers.run` run updates existing records without duplicating them (row count stays the same).

---

## Phase 3 — Frontend

**Goal:** React app connects to local API and renders deal cards with working filters.

Read `docs/frontend.md` before starting.

---

### Task 3.1 — Scaffold

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install @tanstack/react-query tailwindcss @tailwindcss/vite
npx tailwindcss init
```

`vite.config.js` — add API proxy for local dev so `fetch('/api/...')` hits the local FastAPI server:

```js
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

`.env` in `frontend/`:

```
VITE_API_BASE_URL=
```

When `VITE_API_BASE_URL` is empty, requests go to the Vite dev proxy. In production builds, set it to the deployed API URL.

---

### Task 3.2 — API client (`src/api/client.js`)

```js
const BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function fetchBikes(params) {
  const url = new URL(`${BASE}/api/v1/bikes`);
  Object.entries(params).forEach(([k, v]) => {
    if (Array.isArray(v)) v.forEach(val => url.searchParams.append(k, val));
    else if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
  });
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function fetchFilters() {
  const res = await fetch(`${BASE}/api/v1/meta/filters`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}
```

---

### Task 3.3 — Filter state (`src/hooks/useFilters.js`)

Filter state lives exclusively in URL search params. Do not use `useState` for filter values.

```js
import { useSearchParams } from 'react-router-dom';

export function useFilters() {
  const [params, setParams] = useSearchParams();

  const filters = {
    category: params.get('category') || '',
    city: params.get('city') || '',
    size: params.getAll('size'),
    vendor: params.get('vendor') || '',
    min_discount: parseInt(params.get('min_discount') || '0', 10),
    q: params.get('q') || '',
    sort: params.get('sort') || 'discount_desc',
    page: parseInt(params.get('page') || '0', 10),
  };

  const setFilter = (key, value) => {
    setParams(prev => {
      const next = new URLSearchParams(prev);
      if (Array.isArray(value)) {
        next.delete(key);
        value.forEach(v => next.append(key, v));
      } else {
        next.set(key, value);
      }
      next.set('page', '0');  // reset page on filter change
      return next;
    }, { replace: true });
  };

  const clearFilters = () => setParams({}, { replace: true });

  return { filters, setFilter, clearFilters };
}
```

---

### Task 3.4 — `App.jsx` — wire TanStack Query

```jsx
const LIMIT = 50;

export default function App() {
  const { filters, setFilter, clearFilters } = useFilters();

  const bikesQuery = useQuery({
    queryKey: ['bikes', filters],
    queryFn: () => fetchBikes({ ...filters, limit: LIMIT, offset: filters.page * LIMIT }),
    keepPreviousData: true,
  });

  const filtersQuery = useQuery({
    queryKey: ['filters'],
    queryFn: fetchFilters,
    staleTime: 60 * 60 * 1000,
  });

  // pass bikesQuery.data, filtersQuery.data, filters, setFilter, clearFilters down to components
}
```

---

### Task 3.5 — Components

Build components in this order (each is independently testable with dummy data):

**`BikeCard`** — horizontal list row layout (desktop), collapses to card on mobile.

Fields to display: discount badge (`{discount_percentage}% off`), brand + model name, frame_size, price_sale with strikethrough price_original, vendor_name, and a "View Deal →" button linking to `product_url` (opens in new tab).

Image: `<img loading="lazy" width="80" height="80" src={image_url} alt={model_name} />`. If `image_url` is null, render a grey placeholder div with a bicycle SVG icon.

**`BikeGrid`** — renders a list of `BikeCard`. Groups cards by `(vendor_name, brand, model_name)` to avoid 5 identical cards differing only by size. Show one card per model with all available sizes listed as chips; clicking a size chip selects it and adds it to the size filter.

**`FilterStrip`** — sticky bar at top. Contains:
- City dropdown (from `filtersQuery.data.cities`)
- Category dropdown (from `filtersQuery.data.categories`)
- Size multi-select button grid (from `filtersQuery.data.sizes`)
- Min discount slider (0–80, step 5)
- Vendor dropdown (from `filtersQuery.data.vendors`)
- Search input (debounce 300ms before updating URL)

All filter changes call `setFilter(key, value)`.

**`StatsBanner`** — shows `{total} deals · {vendors.length} shops · last updated {last_scraped_at}`.

**`Pagination`** — previous/next buttons + current page indicator. Updates `page` param via `setFilter('page', n)`.

**`LoadingState`** — skeleton cards matching the BikeCard layout.

**`EmptyState`** — "No deals match your filters" with a "Clear all filters" button that calls `clearFilters()`.

**`ErrorState`** — "Could not load deals. Try refreshing." with a retry button.

---

### Task 3.6 — Assemble and verify

Compose all components in `App.jsx`. Verify the following scenarios manually in a browser:

1. Page loads → shows loading state → renders deal cards
2. Selecting a category filter → URL updates → grid re-filters without page reload
3. Selecting multiple sizes → both appear in URL as `?size=M&size=L`
4. Typing in search → URL updates after 300ms → grid filters
5. Min discount slider → only high-discount deals shown
6. Clicking "View Deal →" → opens external URL in new tab
7. Narrowing filters to zero results → EmptyState renders with "Clear filters" CTA
8. Stopping the API server → ErrorState renders
9. Direct URL share: copy URL with filters, open in new tab → same filters active
10. Mobile viewport (375px) → layout adapts (cards stack vertically, filter strip scrolls)

**Phase 3 is done when** all 10 scenarios work correctly against the local API.

---

## Phase 4 — CI/CD and Deployment

**Goal:** Scrapers run daily in GitHub Actions; API and frontend are live on free hosting.

---

### Task 4.1 — GitHub Actions scraper workflow (`.github/workflows/scraper.yml`)

```yaml
name: Daily Scraper

on:
  schedule:
    - cron: '0 2 * * *'   # 2am UTC daily
  workflow_dispatch:        # allow manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python -m scrapers.run
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

If the scraper process exits non-zero, GHA marks the job failed and GitHub sends an email to the repo owner. This is the primary alert mechanism.

Set `DATABASE_URL` as a GitHub Actions secret pointing to Supabase PostgreSQL.

---

### Task 4.2 — Supabase setup

1. Create a Supabase project (free tier).
2. Copy the connection string (`postgresql+asyncpg://...`) from Project Settings → Database → Connection string (URI mode, with `?prepared_statement_cache_size=0` appended for asyncpg compatibility).
3. Run the schema setup once — this creates both tables and all indexes:
   ```bash
   DATABASE_URL=<supabase-url> python -c "
   import asyncio, os
   from sqlalchemy.ext.asyncio import create_async_engine
   from api.models import Base
   async def main():
       engine = create_async_engine(os.environ['DATABASE_URL'])
       async with engine.begin() as conn:
           await conn.run_sync(Base.metadata.create_all)
   asyncio.run(main())
   "
   ```
4. Save the connection string as `DATABASE_URL` in GitHub Actions secrets.

---

### Task 4.3 — API deployment (Render or Railway)

1. Connect the GitHub repo to Render (or Railway).
2. Set `Start Command: uvicorn api.main:app --host 0.0.0.0 --port $PORT`.
3. Set environment variable `DATABASE_URL` to the Supabase connection string.
4. Confirm `GET https://your-api.render.com/api/v1/health` returns `{"status": "ok"}`.

---

### Task 4.4 — Frontend deployment (Cloudflare Pages)

1. Connect the GitHub repo to Cloudflare Pages.
2. Set `Root directory: frontend`, `Build command: npm run build`, `Build output: dist`.
3. Set environment variable `VITE_API_BASE_URL=https://your-api.render.com`.
4. Confirm the deployed frontend loads and calls the production API successfully.

**Phase 4 is done when:**
- A manual GHA workflow trigger completes successfully and data appears in Supabase.
- The production frontend URL loads deal cards served from the production API.

---

## Constraints and invariants (enforce throughout)

These apply at every phase and must never be violated:

1. **No raw SQL strings outside `api/` and `scrapers/db.py`.** All queries go through SQLAlchemy.
2. **No raw dicts across layer boundaries.** Use Pydantic models at every handoff.
3. **A quarantined scraper must not write any bike records.** Check `quarantined` before any DB write.
4. **Filter state lives in the URL.** No `useState` for filter values in the frontend.
5. **Pydantic validation before every DB write.** Invalid records are logged and skipped, not written.
6. **`price_sale > price_original` is a data error.** Log and skip; never write it.
7. **`discount_percentage` is always recomputed on UPSERT.** Never trust a cached value.
8. **One SQLAlchemy ORM definition per table.** `api/models.py` is the single source of truth.
9. **No `.env` files committed.** Use `.env.example` with placeholder values only.
10. **`robots.txt` must be checked** before any scraper makes product requests to a new domain.
