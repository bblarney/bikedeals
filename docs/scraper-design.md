# Scraper Design

Reflects the implementation in `scrapers/` as of the 97-vendor registry. When the
code and this document disagree, the code wins — please fix the document.

---

## Adding a new vendor — required checklist

Most new shops need **no Python at all**: drop a YAML file in `scrapers/vendors/`
and pick an existing pipeline. But a vendor is not actually live until every box
below is ticked. Steps 3 and 4 are the ones that have bitten us.

1. **Write the vendor YAML** — `scrapers/vendors/<slug>.yaml`, matching
   `VendorConfig` (see below). Files starting with `_` are templates and are
   skipped by `load_registry()`.

2. **Verify it in isolation, with no database:**

   ```bash
   python -m scrapers.scrape_check "<Vendor Name>"
   ```

   This runs the real pipeline for one shop and exits non-zero if the scrape
   would fail production's checks (error, >5% invalid records, or zero bikes).
   Check the sample rows it prints: right categories, real frame sizes (not
   colours), sane prices.

3. **Add the vendor's hostname to `ALLOWED_HOSTS` in `worker/worker.js`, and
   redeploy the Worker** (`cd worker && npx wrangler deploy`).

   In CI every request egresses through the Cloudflare Worker proxy, which only
   proxies hosts on its allowlist. Skipping this gives a `403 {"error": "host not
   in allowlist: …"}` on the nightly run *only for the new shops* — everything
   else keeps working, so it reads like a mysterious per-vendor block rather than
   a config omission. `tests/test_worker_allowlist.py` fails the build if the file
   drifts from the registry, but **it cannot detect a stale deploy** — the
   deployed Worker is a separate artifact. Redeploying is a manual step.

4. **If the shop needs a new *pipeline*** (not just a new YAML), see
   "Requirements for a new pipeline" at the end of this document.

5. **Confirm on the next nightly run** — the summary email lists per-vendor
   failures and every warning logged during the run.

---

## Vendor registry

One YAML file per shop in `scrapers/vendors/`, loaded by
`scrapers/registry.py::load_registry()` into a `VendorConfig`
(`scrapers/models.py`):

```python
class VendorConfig(BaseModel):
    vendor_name: str
    city: str | None = None              # single-location vendors
    cities: list[str] | None = None      # national chains: one record per city
    base_url: str
    pipeline: Literal["shopify", "woocommerce", "woocommerce_api",
                      "bigcommerce", "giant", "canyon", "custom"]
    category_map: dict[str, str]         # shop tag -> our category
    selectors: dict[str, str] | None = None          # DOM pipelines only
    collection: str | None = None                    # single Shopify collection
    collections: list[str] | None = None             # curated collections/slugs
    collection_category_map: dict[str, str] | None = None
    max_pages: int | None = None
    shop_path: str = "shop"
    shop_paths: list[str] | None = None              # multi-path stores
    brand_map: dict[str, str] | None = None          # brand-name overrides
```

`cities` fans a national chain out to one record per city. `collection_category_map`
takes precedence over `category_map`: for shops where every product is
`product_type: "Bikes"`, the curated collection a product was found in decides its
category.

---

## Pipelines

Six are implemented; `custom` is declarable but unimplemented and raises
`NotImplementedError`. Dispatch lives in `scrapers/orchestrator.py`.

| Pipeline | Source | Notes |
|---|---|---|
| `shopify` | `/products.json` or `/collections/<handle>/products.json` | Most vendors |
| `woocommerce` | Listing-page DOM via `selectors` | Fallback; one row per product |
| `woocommerce_api` | `/wp-json/wc/store/v1` | Preferred over DOM where reachable |
| `bigcommerce` | Listing-page DOM | |
| `giant` | Giant franchise storefronts | Per-store `vendor_name` to avoid collisions. **`base_url` must use the www host** — see below |
| `canyon` | Canyon direct-to-consumer | Outlet path falls back to URL-segment categories |

### Giant franchise stores — www, and a shared catalogue

Two things about the `giant` pipeline are easy to get wrong, and neither fails
loudly:

- **`base_url` must include `www.`** The apex host 301s a deep path to the site
  root — `giantramsgate.com.au/au/bikes/road-bikes` → `www.giantramsgate.com.au/au`
  — dropping the path. An apex `base_url` therefore scrapes the *homepage's*
  handful of featured tiles once per configured path and dedupes them to a
  single-figure result: Giant Ramsgate returned 6 bikes instead of 130, and
  `scrape_check` still reported PASS because non-zero and 0% invalid is a pass.
- **Category paths drift.** `electric-bikes` was renamed `e-bikes`, which cost
  Ramsgate every E-Bike row while the other paths kept working. The current set
  is `e-bikes`, `road-bikes`, `mountain-bikes`, `cross-and-gravel-bikes`,
  `fitness-and-city-bikes`, `kids-bikes`. Categorise from the `surface-*` CSS
  classes rather than the path: each product carries exactly one, so the
  exact-match pass settles it. Note the path `cross-and-gravel-bikes` and the
  class `cross-gravel-bikes` are spelled differently.

Be aware that every franchise white-labels the **same national catalogue at the
same RRP**, with no sale prices — so each store adds a location, not stock, and
contributes only 0%-discount rows. See `docs/vendors.md` before adding more.

### Shopify pagination — the two cursoring modes

Root and collection endpoints page **differently**, and getting this wrong
silently truncates a shop at 250 products:

- `/products.json` supports `since_id` cursoring — page with `since_id=<last id>`.
- `/collections/<handle>/products.json` **ignores `since_id`** and re-serves page
  one. Page it with `?page=N` instead.

Stop when a page returns fewer than `SHOPIFY_PAGE_SIZE` (250) products, or when
`max_pages` is hit. A guard also drops products whose handle was already seen, so
a looping cursor can't duplicate rows.

### Frame size, not colour

Frame size comes from Shopify's declared size axis in `product.options`,
preferring `"Frame Size"` over `"Wheel Size"`. Do **not** parse it out of the
variant title: colour names like "Forge Grey" or "DISRUPT Camo" share no word with
the size vocabulary and end up in the size filter. A product with no size axis
records `"N/A"` and is kept, not dropped.

### Accessory filtering

Shops file frames, scooters, chargers and helmets under a bike `product_type`.
`_is_accessory()` matches an accessory-word set against both `product_type` and
the title, and those products are skipped before validation.

---

## Rate limiting

Small local shops run on shared hosting. Be a polite scraper:

- **Delay between requests:** `SCRAPER_DELAY_RANGE` = 1–2 s random jitter.
- **Concurrent vendors:** `MAX_CONCURRENT_VENDORS` (default 3, env-overridable).
  Kept low deliberately — parallel bursts from one IP trip Cloudflare bot
  mitigation, which then challenges the rest of the run.
- **Startup jitter:** each vendor waits 0.5–1.5 s after acquiring its slot so
  workers don't fire in lockstep. Off for `scrape_check`.
- **User-Agent:** `BikeGrid-Scraper/1.0 (+https://bikegrid.com.au)`.
- **robots.txt:** checked per host via stdlib `robotparser` before scraping; a
  disallow logs a warning and skips the vendor. Missing/unreachable robots.txt is
  treated as permissive (RFC 9309).

### Retries and Cloudflare challenges

`get_with_retry` retries 429/500/502/503/504 and network errors with exponential
backoff (3 attempts). A Cloudflare bot challenge is the deliberate exception: the
`cf-mitigated` response header means a JS interstitial an httpx client cannot
solve, so `CloudflareChallenge` is raised immediately. Retrying it is not just
useless but harmful — each extra request further degrades our IP reputation.
Sites behind a JS challenge need a challenge-solving egress (residential proxy or
scraping API) and are currently out of scope.

A Cloudflare **block** is the same problem wearing different clothes: a WAF rule
(or a ban) returns a plain 403 with the "Attention Required" page and *no*
`cf-mitigated` header, so it is indistinguishable from a shop's own 403 until the
body is read. `_is_cloudflare_block` checks a 403/429 HTML body for Cloudflare's
own markers and raises the same `CloudflareChallenge` with `mitigation="block"`.
Without it, a zone that blocks our egress on every path — robots.txt included —
surfaces only as "0 bikes scraped", which reads like a broken selector rather
than an egress problem no config change can fix. That is what NRG Cycles was
doing for weeks before it was diagnosed and retired (`docs/vendors.md`).

---

## Egress proxy (CI only)

GitHub Actions egresses from a datacenter IP range that Cloudflare and Shopify
block as a class, so every vendor request in CI is tunnelled through a free
Cloudflare Worker (`worker/worker.js`, documented in `worker/README.md`):

```
GitHub Actions ──(X-Target-URL + X-Proxy-Token)──> Cloudflare Worker ──> vendor
```

`scrapers/utils.py::_apply_proxy` rewrites every request in `get_with_retry` and
`check_robots`. It is a **no-op when `SCRAPER_PROXY_URL` is unset**, so local dev
and tests fetch vendors directly and are unaffected.

The Worker enforces an https-only, hostname-allowlist policy so a leaked token
can't turn it into an open proxy — hence checklist step 3 above.

### Keeping the proxy out of error text

This is a public repo, and scrape errors reach humans through the daily summary
email, `scrape_summary.json`, and CI logs — any of which can be pasted into an
issue or PR. Two mechanisms keep the proxy out of them:

- **`_restore_target_url`** re-points a proxied response's `request` at the vendor
  URL before any caller reads it. Every pipeline calls `resp.raise_for_status()`,
  and httpx builds that message from `resp.request.url` — so without this a
  failure reads `403 Forbidden for url '<the Worker>'`. That both named our
  endpoint and pointed at the wrong host, which is exactly why an allowlist
  omission looked like a proxy fault. The rewrite also **drops `X-Proxy-Token`**,
  which otherwise rides along on the request attached to any raised exception.
- **`redact_proxy`** replaces the endpoint with `<scraper-proxy>` in text that
  can't be fixed structurally: transport-error strings, the `robots.txt` warning,
  `ScrapeResult.error`, and every record the summary's log collector captures
  (including from third-party loggers like httpx).

Both are no-ops when no proxy is configured. If you add a code path that surfaces
an exception to a human, run it through `redact_proxy`.

---

## Quarantine

A vendor is quarantined for a run when it raises, or when its data looks corrupt.
Quarantine means: **write nothing for that vendor**, keep yesterday's data, and
carry on with the rest of the run. A single bad vendor never crashes the run and
never wipes its own inventory.

Three conditions, all in `scrapers/run.py`:

| Condition | `scrape_log.status` | Effect |
|---|---|---|
| Pipeline raised | `quarantined` | No upsert, no `mark_stale` |
| >5% of products failed validation (`QUARANTINE_INVALID_RATIO`) | `quarantined` | No upsert, no `mark_stale` |
| Scrape returned 0 bikes | `empty` | No upsert, no `mark_stale` |

The zero-bikes rule matters: we can't distinguish a genuinely empty shop from a
blocked fetch, and running `mark_stale` on an empty result would flag the
vendor's *entire* inventory out-of-stock on a transient failure.

```sql
CREATE TABLE scrape_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_name     TEXT NOT NULL UNIQUE,   -- one current row per vendor
    run_at          TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL,          -- ok | quarantined | skipped | empty
    error_msg       TEXT,
    bikes_upserted  INTEGER DEFAULT 0,
    last_success_at TIMESTAMPTZ             -- preserved across failing runs
);
```

The row is upserted per vendor, and `last_success_at` is only advanced on `ok` —
so "how long has this vendor been broken?" is answerable from one row.

---

## Alerting

The daily workflow emails a summary after every run (`if: always()`), built from
`scrape_summary.json`. It carries the run duration, ok/failed vendor counts, total
bikes upserted, each failure with its reason, and **every WARNING+ log record
grouped with a count** — so problems that don't sink a whole vendor (retries,
robots.txt skips, category-map misses) stay visible instead of being averaged away.

---

## UPSERT / deduplication

Daily runs UPSERT on `bikes.id`, a 16-char SHA-256 of
`vendor_name::city::product_url::frame_size` (`make_bike_id`). Including city
keeps a national chain's per-city rows distinct.

```sql
INSERT INTO bikes (...) VALUES (...)
ON CONFLICT(id) DO UPDATE SET
    price_sale = excluded.price_sale,
    price_original = excluded.price_original,
    discount_percentage = excluded.discount_percentage,
    in_stock = excluded.in_stock,
    last_seen_at = excluded.last_seen_at;
```

### Price history

`upsert_bikes` appends a `price_events` row only when a bike is **first seen or
its sale price changes** — not a daily snapshot — so the table stays within the
free-tier storage cap while still backing a real price-history timeline. Events
older than `PRICE_EVENT_RETENTION_DAYS` (default 365) are pruned at the end of
each run.

### Stale product handling

After a vendor scrapes successfully, rows for that vendor not seen in this run are
marked out of stock — never deleted, so price history and bookmarked URLs survive:

```sql
UPDATE bikes
SET in_stock = 0
WHERE vendor_name = :vendor
  AND last_seen_at < :run_start_time;
```

---

## Category normalization

Shop tags are free-form ("road", "Road Bikes", "ROAD CYCLING", "drop-bar"). The
per-shop `category_map` resolves them to the five-value enum (`Road`, `Mountain`,
`Gravel`, `E-Bike`, `Commuter`):

```yaml
category_map:
  road: Road
  mtb: Mountain
  trail: Mountain
  gravel: Gravel
  e-bike: E-Bike
  commuter: Commuter
```

There is **no `Other` bucket** — `BikeRecord.category` is a strict `Literal`, and a
product with no category match is dropped rather than guessed at. Because a
misconfigured `category_map` would therefore yield a silent zero-bike scrape, the
Shopify pipeline logs an explicit warning when products were found but none
matched.

`resolve_category` (`scrapers/utils.py`) does two passes over the candidate
strings: exact key match first, then substring match with keys tried
**longest-first**, so `"mountain bikes"` beats `"bikes"` regardless of YAML order.

Where a product belongs to several categories at once, the *pipeline* decides
which candidate is offered first. `woocommerce_api` sorts electric slugs ahead of
the rest (`_is_electric_slug`) so an e-MTB resolves to `E-Bike` rather than
`Mountain`; that check matches on `"electric"`/`"ebike"` after stripping
separators, because a shop filing e-MTBs under `mtb-ebikes` contains neither
"electric" nor "e-bike" literally. Any new pipeline covering shops that
cross-file e-bikes needs the same ordering.

---

## Run orchestration

```
python -m scrapers.run
  ├─ load registry, shuffle vendor order (no vendor permanently starved)
  ├─ alembic upgrade head has already run (Postgres); create_all is SQLite-only
  ├─ for each vendor (async, max 3 concurrent, 0.5–1.5s startup jitter):
  │     ├─ dispatch to pipeline → (list[BikeRecord], invalid_count)
  │     ├─ quarantine checks (raised / >5% invalid / 0 bikes)
  │     ├─ upsert_bikes  → append price_events on change
  │     ├─ mark_stale
  │     └─ write_scrape_log
  ├─ prune_price_events older than the retention window
  └─ write scrape_summary.json  → formatted into the summary email
```

Schedule: `.github/workflows/scrape.yml`, daily at 08:00 UTC, plus
`workflow_dispatch`. Note `create_all` is restricted to SQLite on purpose — running
it against Postgres adds new tables but never altered columns, silently drifting
prod out of Alembic's tracking.

---

## Requirements for a new pipeline

If a shop can't be served by an existing pipeline, a new one must:

1. **Live in `scrapers/pipelines/<name>.py`** exposing
   `async def scrape_<name>(config, client) -> tuple[list[BikeRecord], int]`
   — the second element is the invalid-record count that feeds the quarantine
   ratio. Add the name to the `VendorConfig.pipeline` `Literal` and to the
   dispatch in `orchestrator.py`.

2. **Route every request through `get_with_retry`** (and `check_robots` before
   the first fetch). Never call `client.get` directly: that bypasses the proxy
   rewrite, the retry policy, and Cloudflare-challenge detection in one go.

3. **Let `CloudflareChallenge` propagate.** Don't catch it to return partial
   data — the orchestrator turns it into a clean per-vendor failure that
   preserves existing rows.

4. **Count invalid records rather than dropping them silently**, so a vendor
   whose schema changed trips the 5% quarantine threshold instead of quietly
   halving its inventory.

5. **Return `[]` rather than raising for an empty-but-healthy fetch** — `run.py`
   already treats zero bikes as a failure that preserves existing data.

6. **Respect `SCRAPER_DELAY_RANGE`** between requests within a vendor.

7. **Ship tests** in `tests/` against recorded fixtures, and verify a real shop
   end-to-end with `scrape_check` before merging.

8. **Follow the new-vendor checklist above** — a new pipeline still needs its
   hostnames allowlisted in the Worker and the Worker redeployed.
