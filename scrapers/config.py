import os

SCRAPER_USER_AGENT = "BikeGrid-Scraper/1.0 (+https://bikegrid.com.au)"
SCRAPER_DELAY_RANGE = (1.0, 2.0)
SHOPIFY_PAGE_SIZE = 250

# Optional egress proxy. GitHub Actions' datacenter IP range is blocked as a
# class by Cloudflare/Shopify, so vendor requests are routed through a free
# Cloudflare Worker (see worker/README.md) whose egress IP has good reputation.
# When SCRAPER_PROXY_URL is unset (local dev, tests) requests go direct — the
# proxy path is entirely inert.
SCRAPER_PROXY_URL = os.environ.get("SCRAPER_PROXY_URL")
SCRAPER_PROXY_TOKEN = os.environ.get("SCRAPER_PROXY_TOKEN")
