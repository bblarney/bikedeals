# Vendors

Coverage tracker for shop scrapers. The **source of truth** for what actually
runs is the registry at [`scrapers/vendors/*.yaml`](../scrapers/vendors); this
document records *status* — what is scraped, what could be, and what is blocked.

Vendors are grouped into:

1. **[Scraped](#1-scraped)** — implemented and live in the registry.
2. **[Needs implementation](#2-needs-implementation)** — confirmed scrapable, YAML not yet written.
3. **[Not scraped](#3-not-scraped-blocked)** : blocked, with reason (re-probed 2026-08-30).
4. **[Skipped](#4-skipped)** — no online store, or accessories-only (no complete bikes).

---

## 1. Scraped

108 vendors live in the registry. `pipeline` matches the loader in
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

> **Added 2026-08-30 (96 → 108).** Twelve shops, eleven of which were sitting in
> [Not scraped](#3-not-scraped-blocked) at the time. The headline is a new
> **`lightspeed` pipeline** and the seven shops it unlocks at once: BAM Cycles
> (Melbourne), Evolution Bikes, Wembley Cycles, Lakes Bikes and Bike Force
> Clarkson (Perth), Epic Cycles (Brisbane), Cyclery Northside (Sydney). Every one
> of them was filed here as "JS-rendered products", which was true of the HTML
> and false of the platform: Lightspeed eCom answers `?format=json` on any
> **category** URL with the full listing. The old finding came from testing that
> parameter on the *homepage*, where it returns page metadata and nothing else.
>
> Perth gains four shops in one go, and BAM Cycles is the pick of the twelve at
> 545 bikes with 210 discounted.
>
> These stores are the opposite of the Giant franchise problem described above.
> They carry real markdowns on stock the national chains list at full RRP: the
> Scott Contessa Genius 920 is $3,000 at Bike Force Clarkson and $3,399 at
> Evolution against $6,799.99, undiscounted, at My Ride.
>
> The other five: PM Cycles, Peak Cycles and River City Cycles reached through
> the `woocommerce_api` pipeline (PM Cycles is the Cycle World pattern exactly:
> 403 on the HTML, open on the Store API), plus two Shopify shops, Freedom
> Machine (Byron Bay, the first Northern Rivers vendor, 785 rows with 321
> discounted) and Stealth Electric Bikes.
>
> Deliberately **not** taken, having been probed and found scrapable: Corry
> Cycles, Electric Bike Superstore and Le CycloSportif. All three are dominated
> by 0%-off rows. See their entries below.

> **Retired 2026-08-30 (97 → 96).** George's Bike Shop, the last shop in the
> "registered but not returning data" state, is gone from the registry. It had
> failed all 14 of the nightly runs from 16 to 29 August on the identical
> Cloudflare 403, and every run since it was first diagnosed on 2026-08-04:
> nothing in the repo could have fixed it, because the block is on the egress IP
> class (see its row in [Not scraped](#3-not-scraped-blocked)). Its YAML is
> deleted, its host is out of the Worker allowlist, and migration `595a0ae4dcf0`
> deletes its `bikes`, `price_events` and `scrape_log` rows.
>
> Waiting was the right call for a while: the config is verified working off a
> residential IP, so a change of egress would have revived it with no edits. It
> is retired now because the cost of waiting is not zero. Its rows were frozen at
> the early-August scrape and still flagged in stock, which means a Perth
> catalogue that no longer moves was being served to visitors, counted in the
> facets, and eligible for the daily Instagram pick. If the egress ever gains
> challenge-solving, re-add the YAML (recoverable from this commit) and the
> nightly run repopulates it from scratch.

> **Retired 2026-08-11 (100 → 97).** Cranks, Cycle Co-op and NRG Cycles had each
> been failing every nightly run for weeks, for three unrelated reasons (all
> diagnosed below, in [Not scraped](#3-not-scraped-blocked)). Their YAMLs are
> deleted and their hosts are out of the Worker allowlist.
>
> De-registering a vendor does **not** remove its data: nothing in the run prunes
> rows a config no longer produces, and `mark_stale` only runs for vendors still
> being scraped, so their listings would have sat in the DB with a frozen
> "last seen" date and no way to ever change. Migration `e4b1a72c9d35` deletes
> their `bikes`, `price_events` and `scrape_log` rows. Re-adding any of them
> means re-adding the YAML and letting the nightly run repopulate from scratch.

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
| BAM Cycles | Melbourne | bamcycles.com.au | lightspeed |
| Bay Bike Co | Newcastle | baybikeco.com.au | shopify |
| Bayside Cycles | Melbourne | baysidecycles.com.au | shopify |
| Bicycle Centre Australia | 11 stores (chain) | bicycle-centre.com.au | shopify |
| Bicycle Centre Belmont | Geelong | bicyclecentrebelmont.com.au | shopify |
| Bicycle Express | Adelaide | bicycleexpress.com.au | shopify |
| Bicycle Fix | Adelaide Hills | bicyclefix.com.au | shopify |
| Bicycle Superstore | Melbourne | bicyclesuperstore.com.au | shopify |
| Bicycle Workshop | Melbourne | bicycleworkshop.com.au | shopify |
| Bike Central GC | Gold Coast | bikecentralgc.com.au | shopify |
| Bike Force Clarkson | Perth | bikeforceclarkson.com.au | lightspeed |
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
| Crooze | Brisbane | crooze.com.au | shopify |
| Currumbin Cycles | Gold Coast | currumbincycles.com.au | shopify |
| Curve Cycling | Melbourne | curvecycling.com | shopify |
| Cyclespot | Sydney | cyclespot.com.au | shopify |
| Cyclery Northside | Sydney | cyclerynorthside.com.au | lightspeed |
| Cycle World | Sydney | cycleworld.com.au | woocommerce_api |
| Cycle Zone | Sunshine Coast | cyclezone.com.au | shopify |
| De Grandi Cycle Works | Geelong | degrandi.com.au | shopify |
| Drift Bikes | Newcastle | driftbikes.com.au | shopify |
| eBikes Superstore | Adelaide | ebikessuperstore.com.au | shopify |
| Electric Bikes Brisbane | Brisbane | electricbikesbrisbane.com.au | shopify |
| Empire Cycles | Perth | empirecycles.com.au | shopify |
| Epic Cycles | Brisbane | epiccycles.com.au | lightspeed |
| Evolution Bikes | Perth | evolutionbikes.com.au | lightspeed |
| Fitzroy Cycles | Melbourne | fitzroycycles.com.au | shopify |
| Freedom Machine | Byron Bay | freedommachine.com.au | shopify |
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
| Lakes Bikes | Perth | lakesbikes.com.au | lightspeed |
| Lekker Bikes | 3 stores (chain) | lekkerbikes.com.au | shopify |
| Life Cycle Bikes | Margaret River | lifecyclebikes.com.au | woocommerce_api |
| Live Life Cycling | Brisbane | livelifecycling.com.au | shopify |
| Macarthur Bikes | Sydney | macarthurebikes.com.au | shopify |
| Mackay Cycles | Mackay | mackaycycles.com.au | shopify |
| McBain Cycles | Hobart | mcbaincycles.com.au | shopify |
| Melbourne Bicycles | Melbourne | melbournebicycles.com.au | shopify |
| My Ride | 20+ stores (chain) | myride.com.au | shopify |
| Off Course | Melbourne | offcourse.bike | woocommerce |
| Omafiets | Sydney | omafiets.com.au | shopify |
| Peak Cycles | Melbourne | peakcycles.com.au | woocommerce_api |
| Pedal Heads | Brisbane | pedalheads.com.au | shopify |
| Pedal Inn | Brisbane | pedalinn.au | shopify |
| Pedl | Sydney | pedl.com.au | shopify |
| Planet Cycles | Brisbane | planetcycles.com.au | shopify |
| PM Cycles | Melbourne | pmcycles.com.au | woocommerce_api |
| Progear Bikes | Melbourne | progearbikes.com.au | shopify |
| Reid Cycles | 2 stores (chain) | reidcycles.com.au | shopify |
| Ride Bellerive | Hobart | ride.net.au | shopify |
| Ride 'n' Roll | Gold Coast | ridenroll.com.au | shopify |
| Ride Union Bike Co | Adelaide Hills | rideunionbikeco.com.au | shopify |
| River City Cycles | Brisbane | rivercitycycles.com.au | woocommerce_api |
| Saint Cloud | Melbourne | saintcloud.com.au | shopify |
| Stealth Electric Bikes | Melbourne | stealthelectricbikes.com | shopify |
| Summit Cycles | Melbourne | summitcycles.bike | shopify |
| Supreme Cycles | Sunshine Coast | supremecycles.com.au | shopify |
| The Bicycle Company | Melbourne | thebicyclecompany.com.au | shopify |
| The Bike Shop | Brisbane | thebikeshop.au | shopify |
| The Mountain Biker | Brisbane | themountainbiker.com.au | shopify |
| Treadly Bike Shop | Adelaide | treadlybikeshop.com.au | shopify |
| Velectrix | Sunshine Coast | velectrix.com.au | woocommerce_api |
| Velofix Rozelle | Sydney | velofix.com.au | shopify |
| Venture Cycles | Sunshine Coast | venturecycles.com.au | shopify |
| Wembley Cycles | Perth | wembleycycles.com | lightspeed |
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
2026-08-30; status unchanged unless noted.

> **Unblocked 2026-08-04:** Cycle World and Canberra Cyclery have moved to
> [Scraped](#1-scraped). Both are WooCommerce sites whose *HTML* listings
> defeated us (403s and empty listing prices respectively); both expose the
> WooCommerce Store API at `/wp-json/wc/store/v1`, which the `woocommerce_api`
> pipeline reads directly. Worth re-probing the other WooCommerce entries below
> the same way before writing them off.

| Store | URL | City | Platform | Reason |
|---|---|---|---|---|
| Cranks | cranks.com.au | Sydney | Next.js + Ecwid | **Retired 2026-08-11**, previously scraped. Replatformed off WooCommerce: the old category path still answers 200 with no product markup, and the new storefront server-renders no products anywhere — no `products.json`, no Store API, and per-product JSON-LD with a price but no sale price and no category. The live catalogue reaches the browser only inside a content-hashed Next.js build chunk |
| Cycle Co-op | cycleco-op.au | Canberra | Shopify | **Retired 2026-08-11**, previously scraped. Store closed: the domain returns Cloudflare error 1016 (origin DNS failure, surfaced as HTTP 409) and the Shopify store behind it, `870a95.myshopify.com`, answers "Store unavailable". Canberra is still covered by My Ride, the same shop's former banner |
| George's Bike Shop | georgesbikeshop.com.au | Perth | WooCommerce | **Retired 2026-08-30**, previously scraped. Cloudflare serves a JS bot challenge (403, `cf-mitigated`) to our datacenter egress, on the HTML category pages *and* on `/wp-json/wc/store/v1`, from a GitHub runner directly and through the Worker proxy alike. The mitigation is scoped to the egress IP class rather than to a path, so no endpoint or pipeline choice reaches it; unblocking needs a challenge-solving egress (residential proxy or scraping API). Verified working off an Australian residential IP (430 records / 142 products, 0 invalid) on the `woocommerce_api` pipeline, so a re-add is worth trying the day the egress changes |
| NRG Cycles | nrgcycles.com.au | Brisbane | WooCommerce | **Retired 2026-08-11**, previously scraped. Its Cloudflare zone 403s ("Attention Required", no `cf-mitigated` header) on **every** path — category HTML, the Store API, product pages, `/robots.txt` — from every overseas/datacenter egress tried, while the same requests from an Australian residential IP scrape 65 bikes. A zone-wide source block, so no pipeline or endpoint change reaches it |
| Pushys | pushys.com.au | National (online) | Non-Shopify | **Added 2026-06-21.** Large online retailer; `/products.json` returns HTTP 404 — not Shopify (BigCommerce/custom). No standard product API |
| Hillside Cycles | hillsidecycles.com | Perth (Glen Forrest) | Shopify | **Added 2026-06-21.** Shopify confirmed but `/products.json` returns `{"products":[]}` — empty online catalog; hire/service shop with no online bike sales |
| Cecil Walker | cecilwalker.com.au | Melbourne | BigCommerce | Headless/React; products via JS hash routing; static HTML has no product data |
| Bike Superstore | bikesuperstore.com.au | Canberra | BigCommerce | Cloudflare Bot Management; `/products.json` 404; blocks `httpx` TLS fingerprint |
| MC Cyclery | mccyclery.com.au | Sydney | Sanity headless | Product data from `cdn.sanity.io`; JS-rendered via Sanity CMS |
| The Odd Spoke | theoddspoke.com.au | Sydney | Neto / Maropost | Behind Cloudflare ("Just a moment…", HTTP 403); products via Neto `nloader` JS |
| Glen Parker Cycles | glenparker.com | Perth | BigCommerce | Stencil theme, JS-rendered product grid; page shell has no product data |
| Fastlane Bike Shop | fastlanebikeshop.com.au | Perth | Squarespace | Images from `images.squarespace-cdn.com`; no product API |
| Movement Systems | movementsystems.com.au | Perth | WooCommerce | No products in static HTML — JS-rendered |
| Speedlite Cycles | speedlitecycles.com.au | Perth | WordPress | Brochure site only; no product catalog |
| Mike's Bikes | mikesbikes.com.au | Gold Coast | WordPress | Brochure-style site; no e-commerce catalog |
| eMTB Store | emtbstore.com.au | Gold Coast | GoDaddy OLS | Fully JS-rendered; static HTML has only loading placeholders |
| Bike Society | bikesociety.com.au | Adelaide | Astro / Vercel | **Re-probed 2026-08-30, unchanged.** Migrated off Shopify to a custom Astro site on Vercel; no `/products.json`; still returns HTTP 429 to automated requests (bot firewall) |
| Royal Bikes | royalbikes.com.au | Warrnambool | WooCommerce | Returns HTTP 400 on all automated requests |
| Giant Cairns | giantcairns.com.au | Cairns | Citrus-Lime | Proprietary "Integrated Ecommerce"; no standard product API |
| Blue Cycles Darwin | bluecyclesonline.com.au | Darwin | Unknown | Returns HTTP 404; no accessible product catalog |
| Breakaway Cycles | breakawaycycles.com.au | Morisset (Lake Macquarie) | WordPress | Brochure site; no WooCommerce product catalog |
| Electric Bike Superstore | electricbikesuperstore.com.au | Melbourne | WooCommerce | **Probed 2026-08-30, deliberately not registered.** Store API serves the catalogue cleanly (77 bike rows, stores at Braeside and Glen Huntly, unrelated to Adelaide's eBikes Superstore), but exactly one row in seventy-seven carries a markdown, so it would land as near-pure 0%-off inventory in the best-covered city in the registry |
| Corry Cycles | corrycycles.com.au | Mackay | Shopify | **Unblocked 2026-08-30, deliberately not registered.** Has replatformed onto Shopify since the last probe: `/products.json` serves 404 products (page with `?page=N`, not `since_id`). Left out on quality, not access: of 1,067 bike rows only 18 carry a discount and only 158 are in stock, in a city Mackay Cycles already covers |
| Le CycloSportif | lecyclosportif.com.au | Noosa | Lightspeed eCom | **Unblocked 2026-08-30, deliberately not registered.** Reachable with the new `lightspeed` pipeline, but it is a hire-and-tours business: 16 bikes, 3 in stock, and not one sale price. It would add Noosa to the map and nothing else |
| Pump n Pedals | pumpnpedals.com.au | Cairns | WooCommerce | **Updated 2026-08-30.** The Store API is reachable after all, which is new, but it holds five products and exactly one is a bike, listed as a rental. Cairns needs a different shop, not a different pipeline |

---

## 4. Skipped

No accessible online store, or online catalog is accessories-only (no complete
bikes).

| Store | URL | City | Reason |
|---|---|---|---|
| Abbotsford Cycles | abbotsfordcycles.com.au | Melbourne | **Added 2026-08-05.** WooCommerce Store API reachable and returns ~100 products, but the catalogue is bikepacking bags, racks, locks and touring parts — no complete bikes |
| Chainsmith | chainsmith.com.au | Sydney | Clothing and accessories only; no bikes |
| Coolum Cycles | coolumcycles.com.au | Sunshine Coast | Custom PHP inquiry-only site; no online store |
| Cycling Sports | cyclingsports.com.au | Melbourne | **Added 2026-08-30.** Clean Shopify feed with 4,884 rows and not one complete bicycle: it trades as Le Knicks of Black Rock, Beach Road, and sells cycling clothing |
| Inner City Cycles | innercitycycles.com.au | Sydney | Shopify confirmed but online catalog is helmets, tyres and lights only; no complete bikes |
| Urban Pedaler | urbanpedaler.com.au | Melbourne | Shopify confirmed but online catalog is tyres and components only; no complete bikes |
