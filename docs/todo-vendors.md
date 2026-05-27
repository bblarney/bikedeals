# Vendors — pending scraper development

## Not scrapeable

These stores are permanently blocked, JS-rendered, or have no accessible product catalog.

| Store | URL | City | Platform | Reason |
|---|---|---|---|---|
| BAM Cycles | bamcycles.com.au | Melbourne | Lightspeed eCom | Product listings are client-side JS-rendered; `?format=json` returns page metadata only, no products |
| PM Cycles | pmcycles.com.au | Melbourne | WooCommerce | Returns HTTP 403 on all automated requests |
| Cecil Walker | cecilwalker.com.au | Melbourne | BigCommerce | BigCommerce headless/React setup; products loaded via JS hash routing (`#/filter:custom_discipline:Road`); static HTML has no product data |
| Bike Superstore | bikesuperstore.com.au | Canberra | BigCommerce | Cloudflare Bot Management; static HTML accessible via `urllib` but blocks `httpx` TLS fingerprint (`cf-mitigated: challenge`) |
| Cycle World | cycleworld.com.au | Sydney | Unknown | Returns HTTP 403 on all automated requests |
| Cyclery Northside | cyclerynorthside.com.au | Sydney | Lightspeed eCom | Same platform as BAM Cycles; JS-rendered products |
| MC Cyclery | mccyclery.com.au | Sydney | Sanity headless | Product images from `cdn.sanity.io`; JS-rendered via Sanity CMS |
| The Odd Spoke | theoddspoke.com.au | Sydney | Neto / Maropost | Product listing loaded via Neto `nloader` JS component; zero prices in static HTML |
| Glen Parker Cycles | glenparker.com | Perth | BigCommerce | BigCommerce Stencil theme with JS-rendered product grid; `~697KB` page shell has no product names or prices |
| Wembley Cycles | wembleycycles.com | Perth | Lightspeed eCom | JS-rendered products; shop ID `626853` |
| Evolution Bikes | evolutionbikes.com.au | Perth | Lightspeed eCom | JS-rendered products; shop ID `663013` |
| Fastlane Bike Shop | fastlanebikeshop.com.au | Perth | Squarespace | Images from `images.squarespace-cdn.com`; no product API |
| Lakes Bikes | lakesbikes.com.au | Perth | Lightspeed eCom | JS-rendered products; "Austin Theme" |
| Movement Systems | movementsystems.com.au | Perth | WooCommerce | No products found in static HTML — JS-rendered |
| Speedlite Cycles | speedlitecycles.com.au | Perth | WordPress | Brochure site only; no product catalog exists |
| Canberra Cyclery | canberracyclery.com.au | Canberra | WooCommerce | `data-product_price=""` empty on listing page; prices only on per-product detail pages |
| Mike's Bikes | mikesbikes.com.au | Gold Coast | WordPress | Brochure-style site; no e-commerce catalog |
| eMTB Store | emtbstore.com.au | Gold Coast | GoDaddy OLS | Fully JS-rendered; static HTML contains only loading placeholders |

---

## Skipped (no accessible online store or accessories-only)

| Store | URL | City | Reason |
|---|---|---|---|
| Wooly's Wheels | woolyswheels.com.au | Sydney | Wheel-building specialist; no complete bikes |
| C Cache | ccache.cc | Sydney | Carbon accessories only (valves, wheels); no bikes |
| Chainsmith | chainsmith.com.au | Sydney | Clothing and accessories only; no bikes |
| Coolum Cycles | coolumcycles.com.au | Sunshine Coast | Custom PHP inquiry-only site; no online store |
