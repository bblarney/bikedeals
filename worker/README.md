# Scraper egress proxy (Cloudflare Worker)

The daily scrape runs on GitHub Actions, whose datacenter IP range Cloudflare
and Shopify block as a class — every runner IP gets the same `429` / `403`
challenge, so sharding and slower pacing can't help (see commit `83cb36b`). This
Worker re-issues each vendor request from Cloudflare's own network, whose egress
IPs have good reputation, recovering the Shopify feeds.

The scraper only routes through it when `SCRAPER_PROXY_URL` is set; unset (local
dev, tests) it fetches vendors directly, so this is purely a CI concern.

## How it fits together

```
GitHub Actions ──(X-Target-URL + X-Proxy-Token)──> Cloudflare Worker ──> vendor
```

The client side lives in `scrapers/utils.py::_apply_proxy`, which rewrites every
request in `get_with_retry` and `check_robots`. The Worker (`worker.js`) checks
the token, enforces an https + vendor-hostname allowlist, forwards the request
(including our polite `User-Agent`), and echoes the origin's status plus the
`cf-mitigated`, `Link`, and `Content-Type` headers back faithfully.

## One-time deployment

Requires a **free** Cloudflare account. Run from this `worker/` directory:

```bash
npx wrangler login
npx wrangler secret put PROXY_TOKEN   # paste a long random string
npx wrangler deploy
```

`wrangler deploy` prints the Worker URL, e.g.
`https://bikegrid-scraper-proxy.<your-subdomain>.workers.dev`.

Then add two **GitHub repo secrets** (Settings → Secrets and variables →
Actions):

| Secret | Value |
| --- | --- |
| `SCRAPER_PROXY_URL` | the `https://…workers.dev` URL from `wrangler deploy` |
| `SCRAPER_PROXY_TOKEN` | the same random string you gave `PROXY_TOKEN` |

The Daily Scrape workflow already passes both into the scraper's environment.

## Validate before trusting it (go/no-go)

Point a local run at the deployed Worker and scrape one previously-blocked
Shopify vendor — no database is touched:

```bash
SCRAPER_PROXY_URL="https://…workers.dev" \
SCRAPER_PROXY_TOKEN="…" \
python -m scrapers.scrape_check "Bike Line"
```

Expect `PASS` with a non-zero bike count. If it still returns `429`, Shopify
isn't trusting Cloudflare's egress either — stop and reassess rather than wiring
CI to a non-fix.

## Maintenance

`ALLOWED_HOSTS` in `worker.js` must include any newly added vendor host. **A new
vendor is not scrapeable in CI until the Worker is redeployed** — adding the YAML
alone leaves it failing with the allowlist `403`. When `scrapers/vendors/*.yaml`
changes, regenerate the list (from the repo root), paste it into `worker.js`, and
`npx wrangler deploy`:

```bash
grep -h -i base_url scrapers/vendors/[!_]*.yaml \
  | sed -E 's/.*base_url:\s*//; s/["'"'"']//g; s#https?://(www\.)?##; s#/.*##' \
  | sort -u
```

The `[!_]` glob skips the `_woocommerce-template.yaml` placeholder host.
`tests/test_worker_allowlist.py` fails if the two ever drift apart again.

A request to an un-allowlisted host returns a distinct `403 {"error":"host not
in allowlist: …"}`, which is easy to tell apart from a real vendor block.
