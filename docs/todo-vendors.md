# Vendors — pending scraper development

Stores confirmed real and worth scraping, but require a custom pipeline (not Shopify).

| Store | URL | City | Platform | Notes |
|---|---|---|---|---|
| Epic Cycles | epiccycles.com.au | Brisbane | OpenCart | No public product API; needs HTML scraper targeting category pages |
| Will Ride | willride.com.au | Adelaide | Unknown | Specialized dealer (sister store to Planet Cycles); no accessible Shopify or public product API found |
| River City Cycles | rivercitycycles.com.au | Brisbane | WooCommerce | Needs HTML selectors investigation |
| My Bike Shop | mybikeshop.com.au | Brisbane | WooCommerce | Needs HTML selectors investigation |
| Bike Lab | bikelab.com.au | Brisbane | DUODONE | Proprietary platform; no standard scraping path |
| Pushys | pushys.com.au | Brisbane, Canberra (national) | BigCommerce | V2 REST API requires auth (401); no public product JSON; needs HTML scraper. Multi-location: treat as national chain with `cities` fan-out (Brisbane, Canberra) |
