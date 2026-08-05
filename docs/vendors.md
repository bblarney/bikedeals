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

100 vendors live in the registry. `pipeline` matches the loader in
[`scrapers/pipelines/`](../scrapers/pipelines). Multi-store chains use a `cities`
list (modelled on [`99bikes.yaml`](../scrapers/vendors/99bikes.yaml)).

> **Giant franchise stores share one national catalogue (verified 2026-08-05).**
> Every `giant`-pipeline store white-labels the same Giant/Liv range at the same
> RRP — the same 53 road bikes totalling $402,947 at Adelaide, Ballarat and
> Ramsgate — and the CMS shows no sale prices, so every row is 0% off. They earn
> their place on **location**, not on distinct stock. Only stores adding a city
> the registry did not already cover are registered; the rest of the ~41-store
> network is deliberately left out rather than duplicating one catalogue 19 more
> times. Two apparent Giant stores are not on this CMS at all: Giant Cairns
> (Citrus-Lime, see [Not scraped](#3-not-scraped-blocked)) and Giant Hervey Bay.
>
> Their configs must use the **www** host. The apex 301s a deep path to the site
> root (`giantramsgate.com.au/au/bikes/road-bikes` → `www.…/au`), so an apex
> `base_url` scrapes the homepage's featured tiles for every path — 6 bikes
> instead of 130, and `scrape_check` still reports PASS.

> **Registered but not currently returning data (checked 2026-08-04):**
>
> - **George's Bike Shop** — Cloudflare challenges our datacenter egress
>   (403 `cf-mitigated`) on both the HTML category pages and the Store API,
>   from a GitHub runner directly *and* through the Worker proxy. The block is
>   on the egress IP class, not a path, so it needs a challenge-solving egress
>   to unblock. Its config is on the `woocommerce_api` pipeline and is verified
>   working off a residential IP, so it recovers with no edits if egress changes.
> - **Cycle Co-op** — vendor-side outage, not ours. `cycleco-op.au` returns
>   Cloudflare error 1016 (origin DNS resolution failure, surfaced as HTTP 409)
>   from every egress tried; the domain resolves to Shopify but is no longer
>   attached to a store. The shop is still trading, so this should recover on
>   its own once they reconnect the domain. No config change made.
>
> Both keep their existing rows in the DB — the orchestrator treats a failed
> vendor as "keep the data, skip `mark_stale`" rather than wiping it.

> **Added 2026-08-04 (68 → 77).** ABC Bikes, Woolys Wheels, CCACHE and Cycle
> World (Sydney), Giant Lygon St and Giant South Yarra (Melbourne), West Coast
> Cycles (Perth), Treadly Bike Shop (Adelaide), Canberra Cyclery (Canberra).
> Five had previously been filed as blocked or accessories-only and were
> re-probed successfully: Cycle World and Canberra Cyclery both yielded to the
> `woocommerce_api` (Store API) pipeline, which reaches prices the HTML listings
> withhold; Woolys Wheels, CCACHE and Treadly do stock complete bikes online.

> **Added 2026-08-05 (77 → 100).** Ten independent shops — Bicycle Workshop and
> Fitzroy Cycles (Melbourne), Velofix Rozelle and Wheelhaus (Sydney), Progear
> Bikes and Curve Cycling (Melbourne), Ampd Bros (Gold Coast), Life Cycle Bikes
> (Margaret River, the first South West WA vendor), Velectrix (Sunshine Coast)
> and Lekker Bikes (3-store chain) — plus thirteen Giant franchise stores taken
> only for the regional cities they add (see the note above). Bicycle Workshop
> is the pick of them: 164 bikes with 319 of 549 variants discounted.

| Vendor | Location | Domain | Pipeline |
|---|---|---|---|
| 99 Bikes | 8 stores (chain) | 99bikes.com.au | shopify |
| ABC Bikes | Sydney | abcbikes.com.au | shopify |
| Alchemy Cycle Trader | Melbourne | alchemycycletrader.com.au | shopify |
| Ampd Bros | Gold Coast | ampdbros.com.au | shopify |
| Bay Bike Co | Newcastle | baybikeco.com.au | shopify |
| Bayside Cycles | Melbourne | baysidecycles.com.au | shopify |
| Bicycle Centre Australia | 11 stores (chain) | bicycle-centre.com.au | shopify |
| Bicycle Centre Belmont | Geelong | bicyclecentrebelmont.com.au | shopify |
| Bicycle Express | Adelaide | bicycleexpress.com.au | shopify |
| Bicycle Fix | Adelaide Hills | bicyclefix.com.au | shopify |
| Bicycle Superstore | Melbourne | bicyclesuperstore.com.au | shopify |
| Bicycle Workshop | Melbourne | bicycleworkshop.com.au | shopify |
| Bike Central GC | Gold Coast | bikecentralgc.com.au | shopify |
| Bike Force Joondalup | Perth | bikeforcejoondalup.com.au | shopify |
| Bike Line | Toowoomba | bikeline.com.au | shopify |
| Bike Now | Melbourne | bikenow.com.au | shopify |
| Bikeology | Brisbane | bikeology.com.au | shopify |
| Bikes.com.au | Melbourne | bikes.com.au | shopify |
| Bikes Online | 5 stores (chain) | bikesonline.com.au | shopify |
| Bike Zone Fitzroy | Melbourne | bikezonefitzroy.com.au | shopify |
| Canberra Cyclery | Canberra | canberracyclery.com.au | woocommerce_api |
| Canyon | National (D2C) | canyon.com | canyon |
| CCACHE | Sydney | ccache.cc | shopify |
| Cranks | Sydney | cranks.com.au | woocommerce |
| Crooze | Brisbane | crooze.com.au | shopify |
| Currumbin Cycles | Gold Coast | currumbincycles.com.au | shopify |
| Curve Cycling | Melbourne | curvecycling.com | shopify |
| Cycle Co-op | Canberra | cycleco-op.au | shopify |
| Cyclespot | Sydney | cyclespot.com.au | shopify |
| Cycle World | Sydney | cycleworld.com.au | woocommerce_api |
| Cycle Zone | Sunshine Coast | cyclezone.com.au | shopify |
| De Grandi Cycle Works | Geelong | degrandi.com.au | shopify |
| Drift Bikes | Newcastle | driftbikes.com.au | shopify |
| eBikes Superstore | Adelaide | ebikessuperstore.com.au | shopify |
| Electric Bikes Brisbane | Brisbane | electricbikesbrisbane.com.au | shopify |
| Empire Cycles | Perth | empirecycles.com.au | shopify |
| Fitzroy Cycles | Melbourne | fitzroycycles.com.au | shopify |
| George's Bike Shop | Perth | georgesbikeshop.com.au | woocommerce |
| Giant Bairnsdale | Bairnsdale | giantbairnsdale.com.au | giant |
| Giant Ballarat | Ballarat | giantballarat.com.au | giant |
| Giant Bendigo | Bendigo | giantbendigo.com.au | giant |
| Giant Brisbane | Brisbane | giantbrisbane.com.au | shopify |
| Giant Bundaberg | Bundaberg | giantbundaberg.com.au | giant |
| Giant Castlemaine | Castlemaine | giantcastlemaine.com.au | giant |
| Giant Devonport | Devonport | giantdevonport.com.au | giant |
| Giant Echuca | Echuca | giantechuca.com.au | giant |
| Giant Gold Coast | Gold Coast | giantgoldcoast.com.au | shopify |
| Giant Lygon St | Melbourne | giantlygonst.com.au | shopify |
| Giant Mandurah | Mandurah | giantmandurah.com.au | giant |
| Giant Mudgee | Mudgee | giantmudgee.com.au | giant |
| Giant Osborne Park | Perth | giantosbornepark.com.au | shopify |
| Giant Ramsgate | Sydney | giantramsgate.com.au | giant |
| Giant Rockhampton | Rockhampton | giantrockhampton.com.au | giant |
| Giant South Yarra | Melbourne | giantsthyarra.com.au | shopify |
| Giant St Helens | St Helens | giantsthelens.com | giant |
| Giant Sunshine Coast | Sunshine Coast | giantsunshinecoast.com.au | shopify |
| Giant Sydney | Sydney | giantsydney.com.au | shopify |
| Giant Tamworth | Tamworth | gianttamworth.com.au | giant |
| Giant Tuggerah | Central Coast | gianttuggerah.com.au | giant |
| Giant Wollongong | Wollongong | giantwollongong.com.au | shopify |
| Glowworm Bicycles | Sydney | glowwormbicycles.com.au | shopify |
| Happy Wheels | Sydney | happywheels.com.au | woocommerce |
| Hendry's | Geelong | hendrys.com.au | shopify |
| Ivanhoe Cycles | Melbourne | ivanhoecycles.com.au | shopify |
| Jet Cycles | Sydney | jetcycles.com.au | shopify |
| Just Ride Nerang | Gold Coast | justridenerang.com.au | shopify |
| Lekker Bikes | 3 stores (chain) | lekkerbikes.com.au | shopify |
| Life Cycle Bikes | Margaret River | lifecyclebikes.com.au | woocommerce_api |
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
| Progear Bikes | Melbourne | progearbikes.com.au | shopify |
| Reid Cycles | 2 stores (chain) | reidcycles.com.au | shopify |
| Ride Bellerive | Hobart | ride.net.au | shopify |
| Ride 'n' Roll | Gold Coast | ridenroll.com.au | shopify |
| Ride Union Bike Co | Adelaide Hills | rideunionbikeco.com.au | shopify |
| Saint Cloud | Melbourne | saintcloud.com.au | shopify |
| Summit Cycles | Melbourne | summitcycles.bike | shopify |
| Supreme Cycles | Sunshine Coast | supremecycles.com.au | shopify |
| The Bicycle Company | Melbourne | thebicyclecompany.com.au | shopify |
| The Bike Shop | Brisbane | thebikeshop.au | shopify |
| The Mountain Biker | Brisbane | themountainbiker.com.au | shopify |
| Treadly Bike Shop | Adelaide | treadlybikeshop.com.au | shopify |
| Velectrix | Sunshine Coast | velectrix.com.au | woocommerce_api |
| Velofix Rozelle | Sydney | velofix.com.au | shopify |
| Venture Cycles | Sunshine Coast | venturecycles.com.au | shopify |
| West Coast Cycles | Perth | westcoastcycles.com.au | shopify |
| Wheelhaus | Sydney | wheelhaus.com.au | shopify |
| Wollongong Bike Hub | Wollongong | wollongongbikehub.com.au | shopify |
| Woolys Wheels | Sydney | woolyswheels.com.au | shopify |

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

> **Unblocked 2026-08-04:** Cycle World and Canberra Cyclery have moved to
> [Scraped](#1-scraped). Both are WooCommerce sites whose *HTML* listings
> defeated us (403s and empty listing prices respectively); both expose the
> WooCommerce Store API at `/wp-json/wc/store/v1`, which the `woocommerce_api`
> pipeline reads directly. Worth re-probing the other WooCommerce entries below
> the same way before writing them off.

| Store | URL | City | Platform | Reason |
|---|---|---|---|---|
| Pushys | pushys.com.au | National (online) | Non-Shopify | **Added 2026-06-21.** Large online retailer; `/products.json` returns HTTP 404 — not Shopify (BigCommerce/custom). No standard product API |
| Hillside Cycles | hillsidecycles.com | Perth (Glen Forrest) | Shopify | **Added 2026-06-21.** Shopify confirmed but `/products.json` returns `{"products":[]}` — empty online catalog; hire/service shop with no online bike sales |
| BAM Cycles | bamcycles.com.au | Melbourne | Lightspeed eCom | Product listings are client-side JS-rendered; `/products.json` 404, `?format=json` returns page metadata only |
| PM Cycles | pmcycles.com.au | Melbourne | WooCommerce | Returns HTTP 403 (nginx) on all automated requests |
| Cecil Walker | cecilwalker.com.au | Melbourne | BigCommerce | Headless/React; products via JS hash routing; static HTML has no product data |
| Bike Superstore | bikesuperstore.com.au | Canberra | BigCommerce | Cloudflare Bot Management; `/products.json` 404; blocks `httpx` TLS fingerprint |
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
| Abbotsford Cycles | abbotsfordcycles.com.au | Melbourne | **Added 2026-08-05.** WooCommerce Store API reachable and returns ~100 products, but the catalogue is bikepacking bags, racks, locks and touring parts — no complete bikes |
| Chainsmith | chainsmith.com.au | Sydney | Clothing and accessories only; no bikes |
| Coolum Cycles | coolumcycles.com.au | Sunshine Coast | Custom PHP inquiry-only site; no online store |
| Inner City Cycles | innercitycycles.com.au | Sydney | Shopify confirmed but online catalog is helmets, tyres and lights only; no complete bikes |
| Urban Pedaler | urbanpedaler.com.au | Melbourne | Shopify confirmed but online catalog is tyres and components only; no complete bikes |
