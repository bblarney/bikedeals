# Vendors — pending scraper development

## Scrapable — ready to add

> **Status:** All shops below have been implemented as vendor YAMLs in `scrapers/vendors/`.

All confirmed Shopify via `/products.json?limit=1`. Suggested pipeline: `shopify` for all; multi-city chains use a `cities` list like `99bikes.yaml`.

### Individual shops

| Store | URL | City | Notes |
|---|---|---|---|
| Bicycle Express | bicycleexpress.com.au | Adelaide | 3 locations (City, Norwood, Mitcham); single Shopify store. Cannondale, Trek, Cervélo |
| Treadly Bike Shop | treadlybikeshop.com.au | Adelaide (Norwood) | Commuter/cargo/adventure focus |
| eBikes Superstore | ebikessuperstore.com.au | Adelaide | E-bike specialist; Trek Verve+ confirmed in catalog |
| Ride Union Bike Co | rideunionbikeco.com.au | Adelaide Hills | MTB specialist; Amflow, Santa Cruz. Near Fox Creek Bike Park |
| Bicycle Fix | bicyclefix.com.au | Adelaide Hills | MTB + road; Trek Precaliber confirmed; near Fox Creek / Amy Gillett Bikeway |
| Drift Bikes | driftbikes.com.au | Newcastle | Specialized, Trek, Santa Cruz; ships nationally |
| Bay Bike Co | baybikeco.com.au | Newcastle (Warners Bay) | 50+ years trading; GT, Velectrix confirmed |
| De Grandi Cycle Works | degrandi.com.au | Geelong | Est. 1929; road, MTB, e-bike |
| Bicycle Centre Belmont | bicyclecentrebelmont.com.au | Geelong | Part of Bicycle Centre AU network; Merida, e-MTB |
| Ride Bellerive | ride.net.au | Hobart | Trek, Merida, Norco, Focus; e-bikes confirmed |
| McBain Cycles | mcbaincycles.com.au | Hobart | Giant dealer; Giant Revolt Advanced confirmed |
| Wollongong Bike Hub | wollongongbikehub.com.au | Wollongong | GT, kids bikes; free shipping over $150 |
| Jet Cycles | jetcycles.com.au | Sydney | Central Sydney; Specialized focus |
| Inner City Cycles | innercitycycles.com.au | Sydney | MTB accessories + bikes |
| Bike Zone Fitzroy | bikezonefitzroy.com.au | Melbourne (Fitzroy) | Premium road + gravel; Norco Search C Apex AXS confirmed ($4,999) |
| The Bicycle Company | thebicyclecompany.com.au | Melbourne (Dandenong) | Giant dealer; Giant Stance E+ e-MTB confirmed |
| Urban Pedaler | urbanpedaler.com.au | Melbourne | MTB accessories + bikes; Maxxis, Shimano |
| Supreme Cycles | supremecycles.com.au | Sunshine Coast | Locally owned; e-bikes, road, MTB |
| Mackay Cycles | mackaycycles.com.au | Mackay | Specialized + Trek dealer; ships nationally |

### Multi-city chains

| Store | URL | Cities | Notes |
|---|---|---|---|
| My Ride | myride.com.au | Melbourne (Collingwood, Brunswick), Geelong, Shepparton, Ballarat, Wollongong, Hobart, Launceston, Cairns, Mackay, Rockhampton, Perth (Osborne Park, Cannington), Adelaide (Semaphore, Salisbury), Canberra, Alice Springs | 20+ independently owned stores under one Shopify domain; Scott, Avanti, Malvern Star. Model same as `99bikes.yaml` |
| Bicycle Centre Australia | bicycle-centre.com.au | Melbourne (Fitzroy/Bike Zone, South Morang), Geelong, Warrnambool, Bendigo, Shepparton, Armidale NSW, Hunter Valley NSW, Townsville QLD, Goolwa SA, Burnie TAS, Alice Springs NT | 14+ stores; Merida, Norco, DK BMX. Note: Fitzroy store also has own domain `bikezonefitzroy.com.au` |
| Reid Cycles | reidcycles.com.au | Melbourne (North Melbourne, Windsor, Collingwood, Cheltenham, Tottenham), Brisbane (Woolloongabba) | Own brand + Aventon; affordable commuter/road/MTB. Aventon Aventure 3 eBike confirmed in catalog |

---

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
| Bike Society | bikesociety.com.au | Adelaide | Shopify | `/products.json` returns HTTP 429 on every automated request; rate-limit firewall blocks scraper |
| Royal Bikes | royalbikes.com.au | Warrnambool | WooCommerce | Returns HTTP 400 on all automated requests |
| Giant Cairns | giantcairns.com.au | Cairns | Citrus-Lime | Proprietary "Integrated Ecommerce" by Citrus-Lime Ltd; no standard product API |
| Cycle Zone Darwin | cyclezonedarwin.shop | Darwin | Unknown | `/products.json` returns 404; online store listed as "coming soon" |
| Blue Cycles Darwin | bluecyclesonline.com.au | Darwin | Unknown | Returns HTTP 404; no accessible product catalog |
| Breakaway Cycles | breakawaycycles.com.au | Morisset (Lake Macquarie) | WordPress | Standard WordPress brochure site; no WooCommerce product catalog |
| Epic Cycles | epiccycles.com.au | Brisbane | Unknown | Returns HTTP 404 on `/products.json`; not on Shopify |
| River City Cycles | rivercitycycles.com.au | Brisbane | Unknown | Returns HTTP 404 on `/products.json`; not on Shopify |
| Corry Cycles | corrycycles.com.au | Mackay | Unknown | Returns HTTP 404 on `/products.json`; not on Shopify |
| Le CycloSportif | lecyclosportif.com.au | Noosa | Unknown | Returns HTTP 404 on `/products.json`; not on Shopify |
| Pump n Pedals | pumpnpedals.com.au | Cairns | WordPress | Returns HTTP 404 on `/products.json`; WordPress-based site |

---

## Skipped (no accessible online store or accessories-only)

| Store | URL | City | Reason |
|---|---|---|---|
| Wooly's Wheels | woolyswheels.com.au | Sydney | Wheel-building specialist; no complete bikes |
| C Cache | ccache.cc | Sydney | Carbon accessories only (valves, wheels); no bikes |
| Chainsmith | chainsmith.com.au | Sydney | Clothing and accessories only; no bikes |
| Coolum Cycles | coolumcycles.com.au | Sunshine Coast | Custom PHP inquiry-only site; no online store |
| Treadly Bike Shop | treadlybikeshop.com.au | Adelaide (Norwood) | Shopify confirmed but online catalog is accessories only (locks, lights, hubs); no complete bikes in catalog |
| Inner City Cycles | innercitycycles.com.au | Sydney | Shopify confirmed but online catalog is helmets, tyres and lights only; no complete bikes |
| Urban Pedaler | urbanpedaler.com.au | Melbourne | Shopify confirmed but online catalog is tyres and components only; no complete bikes |
