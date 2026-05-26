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
