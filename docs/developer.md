# Developer Guide

## Pull requests

### Title format

```
<type>: <short description>
```

Types:

| Type | Use for |
|---|---|
| `feat` | New feature or behaviour |
| `fix` | Bug fix |
| `scraper` | Adding or updating a vendor scraper |
| `data` | Schema or migration changes |
| `chore` | Tooling, deps, config, CI |

Examples:
```
feat: add discount slider to filter strip
fix: quarantine scraper on missing frame_size field
scraper: add Trek Australia (Shopify pipeline)
data: add city index to bikes table
```

### Description template

```
## What
One or two sentences on what changed.

## Why
Why this change was needed.

## Testing
How you verified it works (manual steps, test run, screenshots).
```

Keep descriptions short. If the diff is self-explanatory, the what/why can be one line each.

---

## Testing a new vendor scraper

Before committing a new `scrapers/vendors/*.yaml`, run it through the lightweight
scrape tester. It runs the **production** scrape pipeline for one shop and prints
a report — **no database is touched**, nothing is persisted.

```bash
python -m scrapers.scrape_check hendrys            # full run + report
python -m scrapers.scrape_check driftbikes --max-pages 1   # quick check
python -m scrapers.scrape_check "Crooze" --json > out.json # machine-readable
```

The `<vendor>` argument matches the YAML's `vendor_name` ignoring case, spaces
and punctuation (so `hendrys` resolves to `Hendry's`). The report shows bike and
unique-product counts, the category/brand breakdown, price range, stock and
discount coverage, and data-quality flags (missing images, missing frame sizes,
a single-category warning that usually means a broken `category_map`).

The exit code mirrors what a real run would decide: **0** when the scrape would
pass, **1** when it would be quarantined (scrape error or too many invalid
records) or returns zero bikes. A green run here means the vendor is ready to add.

---

## Coding guidelines

**Python**
- Type hints on all function signatures.
- Use Pydantic models at every data boundary (scraper output, API response). No raw dicts passed between layers.
- All database access goes through the SQLAlchemy layer — no raw SQL strings outside of `db/`.

**React**
- Filter state lives in the URL (`useSearchParams`), never in component state.
- Fetch data with TanStack Query. No `useEffect` + `fetch` patterns.

**General**
- One vendor config file per shop (YAML), one scraper file per pipeline type.
- If a scraper fails, it must not write partial data. Validate with Pydantic before any DB write.
