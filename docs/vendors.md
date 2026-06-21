# Vendors

Coverage tracker for shop scrapers. The **source of truth** for what actually
runs is the registry at [`scrapers/vendors/*.yaml`](../scrapers/vendors); this
document records *status* — what is scraped, what could be, and what is blocked.

Vendors are grouped into:

1. **[Scraped](#1-scraped)** — implemented and live in the registry.
2. **[Needs implementation](#2-needs-implementation)** — confirmed scrapable, YAML not yet written.
3. **[Not scraped](#3-not-scraped-blocked)** — blocked, with reason (re-probed 2026-06-21).
4. **[Skipped](#4-skipped)** — no online store, or accessories-only (no complete bikes).

---

## 1. Scraped

68 vendors live in the registry. `pipeline` matches the loader in
[`scrapers/pipelines/`](../scrapers/pipelines). Multi-store chains use a `cities`
list (modelled on [`99bikes.yaml`](../scrapers/vendors/99bikes.yaml)).

| Vendor | Location | Domain | Pipeline |
|---|---|---|---|
| 99 Bikes | 8 stores (chain) | 99bikes.com.au | shopify |
| Alchemy Cycle Trader | Melbourne | alchemycycletrader.com.au | shopify |
| Bay Bike Co | Newcastle | baybikeco.com.au | shopify |
| Bayside Cycles | Melbourne | baysidecycles.com.au | shopify |
| Bicycle Centre Australia | 11 stores (chain) | bicycle-centre.com.au | shopify |
| Bicycle Centre Belmont | Geelong | bicyclecentrebelmont.com.au | shopify |
| Bicycle Express | Adelaide | bicycleexpress.com.au | shopify |
| Bicycle Fix | Adelaide Hills | bicyclefix.com.au | shopify |
| Bicycle Superstore | Melbourne | bicyclesuperstore.com.au | shopify |
| Bike Central GC | Gold Coast | bikecentralgc.com.au | shopify |
| Bike Force Joondalup | Perth | bikeforcejoondalup.com.au | shopify |
| Bike Line | Toowoomba | bikeline.com.au | shopify |
| Bike Now | Melbourne | bikenow.com.au | shopify |
| Bikeology | Brisbane | bikeology.com.au | shopify |
| Bikes.com.au | Melbourne | bikes.com.au | shopify |
| Bikes Online | 5 stores (chain) | bikesonline.com.au | shopify |
| Bike Zone Fitzroy | Melbourne | bikezonefitzroy.com.au | shopify |
| Canyon | National (D2C) | canyon.com | canyon |
| Cranks | Sydney | cranks.com.au | woocommerce |
| Crooze | Brisbane | crooze.com.au | shopify |
| Currumbin Cycles | Gold Coast | currumbincycles.com.au | shopify |
| Cycle Co-op | Canberra | cycleco-op.au | shopify |
| Cyclespot | Sydney | cyclespot.com.au | shopify |
| Cycle Zone | Sunshine Coast | cyclezone.com.au | shopify |
| De Grandi Cycle Works | Geelong | degrandi.com.au | shopify |
| Drift Bikes | Newcastle | driftbikes.com.au | shopify |
| eBikes Superstore | Adelaide | ebikessuperstore.com.au | shopify |
| Electric Bikes Brisbane | Brisbane | electricbikesbrisbane.com.au | shopify |
| Empire Cycles | Perth | empirecycles.com.au | shopify |
| George's Bike Shop | Perth | georgesbikeshop.com.au | woocommerce |
| Giant Brisbane | Brisbane | giantbrisbane.com.au | shopify |
| Giant Gold Coast | Gold Coast | giantgoldcoast.com.au | shopify |
| Giant Osborne Park | Perth | giantosbornepark.com.au | shopify |
| Giant Ramsgate | Sydney | giantramsgate.com.au | giant |
| Giant Sunshine Coast | Sunshine Coast | giantsunshinecoast.com.au | shopify |
| Giant Sydney | Sydney | giantsydney.com.au | shopify |
| Giant Wollongong | Wollongong | giantwollongong.com.au | shopify |
| Glowworm Bicycles | Sydney | glowwormbicycles.com.au | shopify |
| Happy Wheels | Sydney | happywheels.com.au | woocommerce |
| Hendry's | Geelong | hendrys.com.au | shopify |
| Ivanhoe Cycles | Melbourne | ivanhoecycles.com.au | shopify |
| Jet Cycles | Sydney | jetcycles.com.au | shopify |
| Just Ride Nerang | Gold Coast | justridenerang.com.au | shopify |
| Live Life Cycling | Brisbane | livelifecycling.com.au | shopify |
| Macarthur Bikes | Sydney | macarthurebikes.com.au | shopify |
| Mackay Cycles | Mackay | mackaycycles.com.au | shopify |
| McBain Cycles | Hobart | mcbaincycles.com.au | shopify |
| Melbourne Bicycles | Melbourne | melbournebicycles.com.au | shopify |
| My Ride | 20+ stores (chain) | myride.com.au | shopify |
| NRG Cycles | Brisbane | nrgcycles.com.au | woocommerce |
| Off Course | Melbourne | offcourse.bike | woocommerce |
| Omafiets | Sydney | omafiets.com.au | shopify |
| Pedal Heads | Brisbane | pedalheads.com.au | shopify |
| Pedal Inn | Brisbane | pedalinn.au | shopify |
| Pedl | Sydney | pedl.com.au | shopify |
| Planet Cycles | Brisbane | planetcycles.com.au | shopify |
| Reid Cycles | 2 stores (chain) | reidcycles.com.au | shopify |
| Ride Bellerive | Hobart | ride.net.au | shopify |
| Ride 'n' Roll | Gold Coast | ridenroll.com.au | shopify |
| Ride Union Bike Co | Adelaide Hills | rideunionbikeco.com.au | shopify |
| Saint Cloud | Melbourne | saintcloud.com.au | shopify |
| Summit Cycles | Melbourne | summitcycles.bike | woocommerce |
| Supreme Cycles | Sunshine Coast | supremecycles.com.au | shopify |
| The Bicycle Company | Melbourne | thebicyclecompany.com.au | shopify |
| The Bike Shop | Brisbane | thebikeshop.au | shopify |
| The Mountain Biker | Brisbane | themountainbiker.com.au | shopify |
| Venture Cycles | Sunshine Coast | venturecycles.com.au | shopify |
| Wollongong Bike Hub | Wollongong | wollongongbikehub.com.au | shopify |

---

## 2. Needs implementation

Confirmed scrapable but not yet building cleanly with existing pipelines.

> **Implemented 2026-06-21:** Hendry's (Geelong) and Crooze (Brisbane) — both
> Shopify — have moved to [Scraped](#1-scraped). Hendry's uses generic
> `product_type: "Bikes"`, so a new `collection_category_map` field
> (collection handle → category, takes precedence over `category_map`) was
> added to the Shopify pipeline to categorise its bikes by curated collection.

### Cycle Zone Darwin — Darwin (`cyclezonedarwin.shop`)

- **Platform:** Ecwid (store id `84374555`). Previously "coming soon"; now a
  live storefront (re-probed 2026-06-21).
- **Status:** Not yet scrapable with existing pipelines. Products are
  JS-rendered; the Ecwid v3 API (`app.ecwid.com/api/v3/84374555/products`)
  returns HTTP 403 without a public token, and no token is exposed in the page
  or the `script.js` loader.
- **How to scrape:** Requires a **new `ecwid` pipeline** that first obtains a
  storefront public token (rendered at runtime) then pages the v3 products
  endpoint. Non-trivial — only the Darwin market makes it worth doing.

---

## 3. Not scraped (blocked)

Permanently blocked, JS-rendered, or no accessible product catalog. Re-probed
2026-06-21; status unchanged unless noted.

| Store | URL | City | Platform | Reason |
|---|---|---|---|---|
| Pushys | pushys.com.au | National (online) | Non-Shopify | **Added 2026-06-21.** Large online retailer; `/products.json` returns HTTP 404 — not Shopify (BigCommerce/custom). No standard product API |
| Hillside Cycles | hillsidecycles.com | Perth (Glen Forrest) | Shopify | **Added 2026-06-21.** Shopify confirmed but `/products.json` returns `{"products":[]}` — empty online catalog; hire/service shop with no online bike sales |
| BAM Cycles | bamcycles.com.au | Melbourne | Lightspeed eCom | Product listings are client-side JS-rendered; `/products.json` 404, `?format=json` returns page metadata only |
| PM Cycles | pmcycles.com.au | Melbourne | WooCommerce | Returns HTTP 403 (nginx) on all automated requests |
| Cecil Walker | cecilwalker.com.au | Melbourne | BigCommerce | Headless/React; products via JS hash routing; static HTML has no product data |
| Bike Superstore | bikesuperstore.com.au | Canberra | BigCommerce | Cloudflare Bot Management; `/products.json` 404; blocks `httpx` TLS fingerprint |
| Cycle World | cycleworld.com.au | Sydney | WordPress | Returns HTTP 403/404 on automated requests; no product API |
| Cyclery Northside | cyclerynorthside.com.au | Sydney | Lightspeed eCom | JS-rendered products (same platform as BAM) |
| MC Cyclery | mccyclery.com.au | Sydney | Sanity headless | Product data from `cdn.sanity.io`; JS-rendered via Sanity CMS |
| The Odd Spoke | theoddspoke.com.au | Sydney | Neto / Maropost | Behind Cloudflare ("Just a moment…", HTTP 403); products via Neto `nloader` JS |
| Glen Parker Cycles | glenparker.com | Perth | BigCommerce | Stencil theme, JS-rendered product grid; page shell has no product data |
| Wembley Cycles | wembleycycles.com | Perth | Lightspeed eCom | JS-rendered products; shop id `626853` |
| Evolution Bikes | evolutionbikes.com.au | Perth | Lightspeed eCom | JS-rendered products; shop id `663013` |
| Fastlane Bike Shop | fastlanebikeshop.com.au | Perth | Squarespace | Images from `images.squarespace-cdn.com`; no product API |
| Lakes Bikes | lakesbikes.com.au | Perth | Lightspeed eCom | JS-rendered products ("Austin Theme") |
| Movement Systems | movementsystems.com.au | Perth | WooCommerce | No products in static HTML — JS-rendered |
| Speedlite Cycles | speedlitecycles.com.au | Perth | WordPress | Brochure site only; no product catalog |
| Canberra Cyclery | canberracyclery.com.au | Canberra | WooCommerce | Listing prices empty; prices only on per-product detail pages |
| Mike's Bikes | mikesbikes.com.au | Gold Coast | WordPress | Brochure-style site; no e-commerce catalog |
| eMTB Store | emtbstore.com.au | Gold Coast | GoDaddy OLS | Fully JS-rendered; static HTML has only loading placeholders |
| Bike Society | bikesociety.com.au | Adelaide | Astro / Vercel | **Updated 2026-06-21.** Migrated off Shopify to a custom Astro site on Vercel; no `/products.json`; still returns HTTP 429 to automated requests (bot firewall) |
| Royal Bikes | royalbikes.com.au | Warrnambool | WooCommerce | Returns HTTP 400 on all automated requests |
| Giant Cairns | giantcairns.com.au | Cairns | Citrus-Lime | Proprietary "Integrated Ecommerce"; no standard product API |
| Blue Cycles Darwin | bluecyclesonline.com.au | Darwin | Unknown | Returns HTTP 404; no accessible product catalog |
| Breakaway Cycles | breakawaycycles.com.au | Morisset (Lake Macquarie) | WordPress | Brochure site; no WooCommerce product catalog |
| Epic Cycles | epiccycles.com.au | Brisbane | Unknown | **Updated 2026-06-21.** Connection fails (HTTP 000) on automated requests; previously 404 on `/products.json` |
| River City Cycles | rivercitycycles.com.au | Brisbane | WordPress | Site reachable (HTTP 200) but `/products.json` 404; not Shopify |
| Corry Cycles | corrycycles.com.au | Mackay | Unknown | **Updated 2026-06-21.** Connection fails (HTTP 000); previously 404 on `/products.json` |
| Le CycloSportif | lecyclosportif.com.au | Noosa | Unknown | **Updated 2026-06-21.** Connection fails (HTTP 000); previously 404 on `/products.json` |
| Pump n Pedals | pumpnpedals.com.au | Cairns | WordPress | `/products.json` 404; WordPress-based site, no product API |

---

## 4. Skipped

No accessible online store, or online catalog is accessories-only (no complete
bikes).

| Store | URL | City | Reason |
|---|---|---|---|
| Wooly's Wheels | woolyswheels.com.au | Sydney | Wheel-building specialist; no complete bikes |
| C Cache | ccache.cc | Sydney | Carbon accessories only (valves, wheels); no bikes |
| Chainsmith | chainsmith.com.au | Sydney | Clothing and accessories only; no bikes |
| Coolum Cycles | coolumcycles.com.au | Sunshine Coast | Custom PHP inquiry-only site; no online store |
| Treadly Bike Shop | treadlybikeshop.com.au | Adelaide (Norwood) | Shopify confirmed but online catalog is accessories only (locks, lights, hubs); no complete bikes |
| Inner City Cycles | innercitycycles.com.au | Sydney | Shopify confirmed but online catalog is helmets, tyres and lights only; no complete bikes |
| Urban Pedaler | urbanpedaler.com.au | Melbourne | Shopify confirmed but online catalog is tyres and components only; no complete bikes |
