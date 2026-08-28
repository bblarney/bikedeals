"""Endpoint tests for the BikeGrid API (hardened contract)."""
from datetime import datetime, timedelta, timezone

import pytest

from sqlalchemy import select
from sqlalchemy.orm import Session

import api.main as main_module
from api.models import PriceEvent, Subscriber
from tests.conftest import make_bike


def test_health_reports_db_connected(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "connected"}


def test_bikes_empty(client):
    r = client.get("/api/v1/bikes")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["results"] == []
    assert r.headers["cache-control"] == "max-age=300"


def test_bikes_returns_seeded_row(client, seed):
    seed()
    r = client.get("/api/v1/bikes")
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["brand"] == "Trek"


def test_bikes_filter_by_category(client, seed):
    seed(
        make_bike(id="road", category="Road"),
        make_bike(id="mtb", category="Mountain", product_url="https://x/2"),
    )
    r = client.get("/api/v1/bikes", params={"category": "Mountain"})
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["category"] == "Mountain"


def test_bikes_min_discount_filter(client, seed):
    seed(
        make_bike(id="lo", discount_percentage=10),
        make_bike(id="hi", discount_percentage=40, product_url="https://x/2"),
    )
    r = client.get("/api/v1/bikes", params={"min_discount": 30})
    assert [b["id"] for b in r.json()["results"]] == ["hi"]


def test_bikes_search_query_matches_brand(client, seed):
    seed(
        make_bike(id="trek", brand="Trek"),
        make_bike(id="giant", brand="Giant", product_url="https://x/2"),
    )
    r = client.get("/api/v1/bikes", params={"q": "gia"})
    assert [b["id"] for b in r.json()["results"]] == ["giant"]


def test_search_query_over_max_length_rejected(client):
    r = client.get("/api/v1/bikes", params={"q": "x" * 101})
    assert r.status_code == 422


def test_excludes_out_of_stock_by_default(client, seed):
    seed(make_bike(id="oos", in_stock=False))
    assert client.get("/api/v1/bikes").json()["total"] == 0


def test_filters_and_stats_ok(client, seed):
    seed()
    assert client.get("/api/v1/meta/filters").status_code == 200
    assert client.get("/api/v1/meta/stats").status_code == 200


def test_subscribe_returns_body_and_rejects_duplicate(client):
    r = client.post("/api/v1/subscribe", json={"email": "rider@example.com"})
    assert r.status_code == 201
    assert r.json() == {"message": "Subscribed"}

    dup = client.post("/api/v1/subscribe", json={"email": "rider@example.com"})
    assert dup.status_code == 409


def test_subscribe_rejects_invalid_email(client):
    assert client.post("/api/v1/subscribe", json={"email": "not-an-email"}).status_code == 422


def test_unsubscribe_is_post_with_token(client, sync_engine):
    client.post("/api/v1/subscribe", json={"email": "bye@example.com"})
    with Session(sync_engine) as s:
        token = s.execute(select(Subscriber.token)).scalar_one()

    # The old state-changing GET route must not exist.
    assert client.get(f"/api/v1/unsubscribe/{token}").status_code == 404

    ok = client.post("/api/v1/unsubscribe", json={"token": token})
    assert ok.status_code == 200
    assert ok.json() == {"message": "Unsubscribed"}

    # Token is gone now.
    assert client.post("/api/v1/unsubscribe", json={"token": token}).status_code == 404


def test_click_increments_and_404s_for_unknown(client, seed):
    seed(make_bike(id="clickme"))
    assert client.post("/api/v1/bikes/clickme/click").status_code == 204
    assert client.post("/api/v1/bikes/nope/click").status_code == 404


def test_bike_detail_404_for_unknown(client):
    assert client.get("/api/v1/bikes/nope").status_code == 404


def test_bike_detail_no_sku_returns_self_offer(client, seed):
    seed(make_bike(id="solo"))
    body = client.get("/api/v1/bikes/solo").json()
    assert body["id"] == "solo"
    assert body["shop_count"] == 1
    assert body["lowest_price"] == 1500.0
    assert len(body["offers"]) == 1
    assert body["offers"][0]["bike_id"] == "solo"


def test_bike_detail_compares_shops_cheapest_first(client, seed):
    # Same SKU at two shops + a second (pricier) size at the cheaper shop.
    seed(
        make_bike(id="a-m", sku="SKU1", vendor_name="Shop A", city="Sydney",
                  frame_size="M", price_sale=1500.0, product_url="https://x/am"),
        make_bike(id="a-l", sku="SKU1", vendor_name="Shop A", city="Sydney",
                  frame_size="L", price_sale=1600.0, product_url="https://x/al"),
        make_bike(id="b-m", sku="SKU1", vendor_name="Shop B", city="Perth",
                  frame_size="M", price_sale=1400.0, product_url="https://x/bm"),
    )
    body = client.get("/api/v1/bikes/a-m").json()
    # One row per shop (cheapest variant), sorted cheapest first.
    assert body["shop_count"] == 2
    assert body["lowest_price"] == 1400.0
    assert [o["vendor_name"] for o in body["offers"]] == ["Shop B", "Shop A"]
    assert [o["price_sale"] for o in body["offers"]] == [1400.0, 1500.0]
    assert body["sku_vendor_count"] == 2


def test_bike_detail_excludes_out_of_stock_offers(client, seed):
    seed(
        make_bike(id="in", sku="SKU2", vendor_name="Shop A", city="Sydney",
                  price_sale=1500.0, product_url="https://x/in"),
        make_bike(id="out", sku="SKU2", vendor_name="Shop B", city="Perth",
                  price_sale=1000.0, in_stock=False, product_url="https://x/out"),
    )
    body = client.get("/api/v1/bikes/in").json()
    assert body["shop_count"] == 1
    assert [o["vendor_name"] for o in body["offers"]] == ["Shop A"]


def test_bike_detail_lists_size_variants(client, seed):
    # Same model in two sizes (+ a pricier duplicate of M at another shop).
    seed(
        make_bike(id="m1", model_name="Domane SL5", frame_size="M",
                  price_sale=1500.0, product_url="https://x/m1"),
        make_bike(id="l1", model_name="Domane SL5", frame_size="L",
                  price_sale=1600.0, product_url="https://x/l1"),
        make_bike(id="m2", model_name="Domane SL5", frame_size="M",
                  vendor_name="Other Cycles", price_sale=1550.0, product_url="https://x/m2"),
    )
    body = client.get("/api/v1/bikes/m1").json()
    # One entry per size (cheapest), current size included, ordered on the size
    # scale. Sorting these alphabetically listed a size picker as L, M, S, XL.
    assert [(v["frame_size"], v["bike_id"]) for v in body["variants"]] == [
        ("M", "m1"), ("L", "l1"),
    ]


def test_price_history_404_for_unknown(client):
    assert client.get("/api/v1/bikes/nope/price-history").status_code == 404


def test_price_history_empty_for_bike_without_events(client, seed):
    seed(make_bike(id="noevents"))
    r = client.get("/api/v1/bikes/noevents/price-history")
    assert r.status_code == 200
    assert r.json() == []


def test_price_history_returns_points_ascending(client, seed, sync_engine):
    seed(make_bike(id="tracked"))
    now = datetime.now(timezone.utc)
    with Session(sync_engine) as s:
        # Insert out of chronological order to prove the endpoint sorts.
        s.add_all([
            PriceEvent(bike_id="tracked", price_sale=1400.0, price_original=2000.0,
                       observed_at=now),
            PriceEvent(bike_id="tracked", price_sale=2000.0, price_original=2000.0,
                       observed_at=now - timedelta(days=10)),
        ])
        s.commit()
    body = client.get("/api/v1/bikes/tracked/price-history").json()
    assert [p["price_sale"] for p in body] == [2000.0, 1400.0]
    assert body[0]["price_original"] == 2000.0


def test_sort_by_saving_ranks_on_dollars_not_percent(client, seed):
    """Dollars off and percent off are different questions, and rank differently.

    The cheap bike wins on discount_percentage (60% against 20%) and loses badly
    on money saved ($360 against $2,600), which is the whole reason the sort
    exists.
    """
    seed(
        make_bike(id="cheap", brand="Apollo", model_name="Trace 10", sku="c1",
                  price_original=600.0, price_sale=240.0, discount_percentage=60,
                  product_url="https://x/c"),
        make_bike(id="dear", brand="Norco", model_name="Search C", sku="d1",
                  price_original=13000.0, price_sale=10400.0, discount_percentage=20,
                  product_url="https://x/d"),
    )
    by_percent = client.get("/api/v1/bikes?sort=discount_desc").json()["results"]
    assert [b["id"] for b in by_percent] == ["cheap", "dear"]

    by_saving = client.get("/api/v1/bikes?sort=saving_desc").json()["results"]
    assert [b["id"] for b in by_saving] == ["dear", "cheap"]


def test_sort_by_saving_treats_an_undiscounted_bike_as_zero(client, seed):
    """price_original is null on anything never discounted, and null sorts badly.

    Without the coalesce the undiscounted bike sorts as NULL, which Postgres
    ranks FIRST on a DESC order: the full-price bike would head a feed sorted by
    biggest saving.
    """
    seed(
        make_bike(id="full", brand="Giant", model_name="Escape 2", sku="f1",
                  price_original=None, price_sale=900.0, discount_percentage=0,
                  product_url="https://x/f"),
        make_bike(id="cut", brand="Merida", model_name="Silex 8000", sku="g1",
                  price_original=1200.0, price_sale=900.0, discount_percentage=25,
                  product_url="https://x/g"),
    )
    results = client.get("/api/v1/bikes?sort=saving_desc").json()["results"]
    assert [b["id"] for b in results] == ["cut", "full"]


def test_unknown_sort_is_rejected(client, seed):
    seed()
    assert client.get("/api/v1/bikes?sort=nonsense_desc").status_code == 422


def test_sitemap_lists_bike_urls(client, seed):
    seed(make_bike(id="mapme"))
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]
    assert "/bikes/mapme" in r.text


# --- cross-shop matching: the two ways it used to lie -----------------------
#
# Both of these are regressions against real data in the live feed, not
# hypotheticals. See scrapers.models.make_product_key.

def test_same_sku_different_brand_is_not_the_same_product(client, seed):
    """A SKU shared by two brands must never merge into one product.

    Shops running the same Lightspeed/Retail POS emit colliding auto-increment
    SKUs. Live example: 210000015200 is a $1,299 Jamis Renegade at one shop and
    a $9,999 AMFLOW PX Carbon at another. Matching on sku alone quoted the Jamis
    price as the AMFLOW's lowest_price, on the page and in its JSON-LD.
    """
    seed(
        make_bike(id="jamis", sku="210000015200", brand="Jamis",
                  model_name="Renegade A1", vendor_name="Melbourne Bicycles",
                  city="Melbourne", price_sale=1299.0, product_url="https://x/j"),
        make_bike(id="amflow", sku="210000015200", brand="Amflow",
                  model_name="PX Carbon", vendor_name="Summit Cycles",
                  city="Sydney", price_sale=9999.0, product_url="https://x/a"),
    )
    body = client.get("/api/v1/bikes/amflow").json()
    assert body["shop_count"] == 1
    assert body["lowest_price"] == 9999.0, "the Jamis price must not leak in"
    assert [o["vendor_name"] for o in body["offers"]] == ["Summit Cycles"]
    assert body["sku_vendor_count"] == 0

    # And the feed must not badge either one as comparable.
    feed = client.get("/api/v1/bikes").json()
    assert {b["sku_vendor_count"] for b in feed["results"]} == {0}


def test_one_chain_across_cities_counts_as_one_vendor(client, seed):
    """Storefronts are not competing offers.

    A chain lists one national catalogue at one price, so counting (vendor, city)
    pairs claimed "available at 21 shops" for a product carried by 4 vendors.
    """
    seed(
        *[
            make_bike(id=f"99-{c}", sku="MEKI2192036", brand="Merida",
                      vendor_name="99 Bikes", city=c, price_sale=1200.0,
                      product_url=f"https://x/99/{c}")
            for c in ("Sydney", "Melbourne", "Brisbane", "Hobart")
        ],
        make_bike(id="indie", sku="MEKI2192036", brand="Merida",
                  vendor_name="Fitzroy Cycles", city="Melbourne",
                  price_sale=1150.0, product_url="https://x/fitz"),
    )
    body = client.get("/api/v1/bikes/99-Sydney").json()

    # Two vendors, not five storefronts.
    assert body["shop_count"] == 2
    assert [o["vendor_name"] for o in body["offers"]] == ["Fitzroy Cycles", "99 Bikes"]
    assert body["lowest_price"] == 1150.0
    assert body["sku_vendor_count"] == 2

    # The collapsed chain row still reports where the rest of the stock is.
    chain = next(o for o in body["offers"] if o["vendor_name"] == "99 Bikes")
    assert chain["location_count"] == 4
    assert next(o for o in body["offers"] if o["vendor_name"] == "Fitzroy Cycles")["location_count"] == 1


def test_feed_carries_the_cheapest_price_across_shops(client, seed):
    """The cross-shop line on a card quotes a floor price, so the feed ships one.

    It rides on the aggregate sku_vendor_count already needs, and covers the
    same rows: every in-stock listing of the product at any shop, this listing
    included. So the cheapest row quotes its own price, which is what lets the
    card say "none cheaper" rather than overclaiming a win.
    """
    seed(
        make_bike(id="dear", sku="SKU9", brand="Trek", vendor_name="Shop A",
                  city="Sydney", price_sale=1800.0, product_url="https://x/dear"),
        make_bike(id="cheap", sku="SKU9", brand="Trek", vendor_name="Shop B",
                  city="Perth", price_sale=1650.0, product_url="https://x/cheap"),
    )
    by_id = {b["id"]: b for b in client.get("/api/v1/bikes").json()["results"]}
    assert by_id["dear"]["sku_min_price"] == 1650.0
    assert by_id["cheap"]["sku_min_price"] == 1650.0
    assert by_id["dear"]["sku_vendor_count"] == 2


def test_feed_quotes_no_cross_shop_price_without_a_cross_shop_match(client, seed):
    """No match, no number. A lone listing must not quote itself as a floor."""
    seed(
        make_bike(id="alone", sku="SKU8", vendor_name="Shop A",
                  product_url="https://x/alone"),
        make_bike(id="nosku", sku=None, vendor_name="Shop B",
                  product_url="https://x/nosku"),
    )
    results = client.get("/api/v1/bikes").json()["results"]
    assert {b["sku_min_price"] for b in results} == {None}


def test_cross_shop_price_ignores_out_of_stock_listings(client, seed):
    """A floor price nobody can buy is a lie, and the count already excludes it."""
    seed(
        make_bike(id="live", sku="SKU7", brand="Trek", vendor_name="Shop A",
                  price_sale=1800.0, product_url="https://x/live"),
        make_bike(id="alsolive", sku="SKU7", brand="Trek", vendor_name="Shop B",
                  price_sale=1750.0, product_url="https://x/alsolive"),
        make_bike(id="gone", sku="SKU7", brand="Trek", vendor_name="Shop C",
                  price_sale=1200.0, in_stock=False, product_url="https://x/gone"),
    )
    by_id = {b["id"]: b for b in client.get("/api/v1/bikes").json()["results"]}
    assert by_id["live"]["sku_min_price"] == 1750.0
    assert by_id["live"]["sku_vendor_count"] == 2


def test_product_key_filter_beats_sku_filter_on_collisions(client, seed):
    seed(
        make_bike(id="jamis", sku="COLLIDE", brand="Jamis", model_name="Renegade",
                  vendor_name="Shop A", price_sale=1299.0, product_url="https://x/j"),
        make_bike(id="amflow", sku="COLLIDE", brand="Amflow", model_name="PX",
                  vendor_name="Shop B", price_sale=9999.0, product_url="https://x/a"),
    )
    # The legacy sku filter still returns both (kept for shared links).
    assert client.get("/api/v1/bikes?sku=COLLIDE").json()["total"] == 2
    # product_key separates them.
    body = client.get("/api/v1/bikes?product_key=jamis:COLLIDE").json()
    assert body["total"] == 1
    assert body["results"][0]["id"] == "jamis"


def test_listing_without_sku_has_no_product_key_and_stands_alone(client, seed):
    seed(
        make_bike(id="n1", sku=None, vendor_name="Shop A", price_sale=1000.0,
                  product_url="https://x/1"),
        make_bike(id="n2", sku=None, vendor_name="Shop B", price_sale=900.0,
                  product_url="https://x/2"),
    )
    body = client.get("/api/v1/bikes/n1").json()
    assert body["product_key"] is None
    assert body["shop_count"] == 1
    assert body["sku_vendor_count"] == 0


# --- the size filter works on the canonical scale ---------------------------

def test_size_filter_matches_every_spelling_of_one_size(client, seed):
    """The live facet had thirty spellings of Large. Picking one must return all."""
    seed(
        make_bike(id="a", frame_size="L", product_url="https://x/a"),
        make_bike(id="b", frame_size="LARGE - 56", product_url="https://x/b"),
        make_bike(id="c", frame_size="Large 29\" Wheels", product_url="https://x/c"),
        make_bike(id="d", frame_size="LRG", product_url="https://x/d"),
        make_bike(id="e", frame_size="M", product_url="https://x/e"),
    )
    body = client.get("/api/v1/bikes", params={"size": "L"}).json()
    assert body["total"] == 4
    assert {b["id"] for b in body["results"]} == {"a", "b", "c", "d"}


def test_size_filter_still_honours_a_bookmarked_raw_value(client, seed):
    # A link shared before sizes were normalised said ?size=Large.
    seed(make_bike(id="a", frame_size="LARGE - 56"))
    assert client.get("/api/v1/bikes", params={"size": "Large"}).json()["total"] == 1


def test_size_filter_on_a_non_size_matches_nothing(client, seed):
    seed(make_bike(id="a", frame_size="L"))
    body = client.get("/api/v1/bikes", params={"size": "Chrome Blue"}).json()
    assert body["total"] == 0, "must not silently ignore the filter and return everything"


def test_size_facet_is_deduped_and_ordered_on_the_scale(client, seed):
    seed(
        make_bike(id="a", frame_size="LARGE", product_url="https://x/a"),
        make_bike(id="b", frame_size="Lg", product_url="https://x/b"),
        make_bike(id="c", frame_size="XS", product_url="https://x/c"),
        make_bike(id="d", frame_size="MEDIUM", product_url="https://x/d"),
        make_bike(id="e", frame_size="54cm", product_url="https://x/e"),
        make_bike(id="f", frame_size="16 inch", product_url="https://x/f"),
        # Neither of these names a size, so neither should pad the dropdown.
        make_bike(id="g", frame_size="N/A", product_url="https://x/g"),
        make_bike(id="h", frame_size="Chrome Blue", product_url="https://x/h"),
    )
    sizes = client.get("/api/v1/meta/filters").json()["sizes"]
    assert sizes == ["XS", "M", "L", "54cm", '16"']


def test_raw_size_is_still_returned_for_display(client, seed):
    seed(make_bike(id="a", frame_size="LARGE - 56"))
    bike = client.get("/api/v1/bikes").json()["results"][0]
    assert bike["frame_size"] == "LARGE - 56"
    assert bike["frame_size_canonical"] == "L"

# --- chain storefronts are one listing, not N ------------------------------
#
# scrapers/pipelines/shopify.py fans a national chain out to one record per
# city, copying product_url and frame_size and varying only city and id. The
# feed showed every copy: three chains alone (99 Bikes x8, Bicycle Centre x11,
# Bikes Online x5) were 44% of the live catalogue. These seed rows mirror that
# fan-out exactly.

def _chain_rows(cities, *, product_url="https://x/chain/propel", **overrides):
    # id mirrors make_bike_id's inputs (vendor, url, size, city) closely enough
    # to stay unique per storefront, which is the whole point of the fan-out.
    tag = f"{product_url.rsplit('/', 1)[-1]}-{overrides.get('frame_size', 'M')}"
    return [
        make_bike(
            id=f"chain-{tag}-{c}", vendor_name="99 Bikes", city=c,
            product_url=product_url, **overrides,
        )
        for c in cities
    ]


def test_chain_storefronts_collapse_to_one_feed_row(client, seed):
    seed(*_chain_rows(["Sydney", "Melbourne", "Brisbane", "Hobart"]))
    body = client.get("/api/v1/bikes").json()

    assert body["total"] == 1, "one listing at four shopfronts is one listing"
    assert len(body["results"]) == 1
    assert body["results"][0]["location_count"] == 4


def test_collapsed_row_is_the_cheapest_storefront(client, seed):
    rows = _chain_rows(["Sydney", "Melbourne"])
    rows[0].price_sale = 1400.0   # Sydney
    rows[1].price_sale = 1200.0   # Melbourne undercuts
    seed(*rows)

    result = client.get("/api/v1/bikes").json()["results"][0]
    assert result["price_sale"] == 1200.0
    assert result["city"] == "Melbourne"


def test_city_filter_narrows_before_collapsing(client, seed):
    seed(*_chain_rows(["Sydney", "Melbourne", "Brisbane"]))
    body = client.get("/api/v1/bikes", params={"city": "Brisbane"}).json()

    assert body["total"] == 1
    assert body["results"][0]["city"] == "Brisbane"
    # In Brisbane it really is one shop, so there is no "+N more" to show.
    assert body["results"][0]["location_count"] == 1


def test_collapse_keeps_distinct_products_apart(client, seed):
    seed(
        *_chain_rows(["Sydney", "Melbourne"], product_url="https://x/a", frame_size="M"),
        *_chain_rows(["Sydney", "Melbourne"], product_url="https://x/a", frame_size="L"),
        *_chain_rows(["Sydney", "Melbourne"], product_url="https://x/b", frame_size="M"),
    )
    body = client.get("/api/v1/bikes").json()

    assert body["total"] == 2, "one product in two sizes, plus a second product"
    assert {b["location_count"] for b in body["results"]} == {2}


def test_same_product_at_two_vendors_is_not_collapsed(client, seed):
    seed(
        make_bike(id="a", vendor_name="Shop A", product_url="https://x/p"),
        make_bike(id="b", vendor_name="Shop B", product_url="https://x/p"),
    )
    assert client.get("/api/v1/bikes").json()["total"] == 2


def test_total_bikes_matches_the_collapsed_feed(client, seed):
    seed(*_chain_rows(["Sydney", "Melbourne", "Brisbane", "Hobart"]))
    # The header's trust number and the feed must not disagree.
    assert client.get("/api/v1/meta/filters").json()["total_bikes"] == 1
    assert client.get("/api/v1/meta/stats").json()["new_today"] == 1


def test_sitemap_advertises_one_url_per_listing(client, seed):
    seed(*_chain_rows(["Sydney", "Melbourne", "Brisbane", "Hobart"]))
    sitemap = client.get("/sitemap.xml").text
    feed_id = client.get("/api/v1/bikes").json()["results"][0]["id"]

    assert sitemap.count("/bikes/") == 1
    # Same pick order as the feed, or we advertise a URL the site doesn't link.
    assert f"/bikes/{feed_id}" in sitemap


# --- size variants are one card, not N -------------------------------------
#
# A shop publishes each size (and on Shopify each colourway) as its own variant
# with its own ?variant= URL. Measured over 2,000 live rows sorted the way the
# site opens, 49% of the feed was the same bike again in another size: page one
# of "best deals" was six consecutive cards of one Giant Revolt X Advanced Pro.

def _variant_rows(sizes, *, path="https://x/p/revolt", vendor="Test Cycles", **overrides):
    """One row per size, spelled the way Shopify spells them: shared path,
    per-variant query string."""
    return [
        make_bike(
            id=f"var-{vendor}-{path[-6:]}-{i}", vendor_name=vendor,
            product_url=f"{path}?variant={100 + i}", frame_size=s, **overrides,
        )
        for i, s in enumerate(sizes)
    ]


def test_sizes_of_one_product_collapse_to_one_card(client, seed):
    seed(*_variant_rows(["S", "M", "L", "XL"]))
    body = client.get("/api/v1/bikes").json()

    assert body["total"] == 1, "four sizes of one bike is one bike"
    # Smallest first, so the chip row reads the way a size chart does.
    assert body["results"][0]["sizes"] == ["S", "M", "L", "XL"]


def test_variant_query_string_does_not_defeat_the_collapse(client, seed):
    # The whole reason the key uses the URL *path*: Shopify puts the variant id
    # in the query, so the raw product_url is per-variant and never matches.
    rows = _variant_rows(["S", "M"])
    assert rows[0].product_url != rows[1].product_url
    seed(*rows)

    assert client.get("/api/v1/bikes").json()["total"] == 1


def test_colourways_of_one_size_collapse_without_duplicating_the_chip(client, seed):
    # One live Bikes Online product was 13 feed rows: 3 sizes in assorted
    # colours, each its own variant, all at one price.
    seed(*_variant_rows(["M", "M", "M", "S"]))
    result = client.get("/api/v1/bikes").json()["results"][0]

    assert result["sizes"] == ["S", "M"], "a size stocked in three colours is one size"


def test_collapsed_card_fronts_the_cheapest_size(client, seed):
    rows = _variant_rows(["S", "M", "L"])
    rows[0].price_sale = 2000.0
    rows[1].price_sale = 1500.0   # M undercuts
    rows[2].price_sale = 2000.0
    seed(*rows)

    result = client.get("/api/v1/bikes").json()["results"][0]
    assert result["price_sale"] == 1500.0, "headline a price a buyer can pay"
    assert result["frame_size"] == "M"
    assert result["sizes"] == ["S", "M", "L"], "the other sizes are still offered"


def test_same_model_at_two_urls_is_not_collapsed(client, seed):
    # The conservative half of the key. A shop that lists one bike twice under
    # two URLs is a real problem, but a different one — and two genuinely
    # different products can share a brand and a model_name.
    seed(
        *_variant_rows(["S", "M"], path="https://x/p/revolt"),
        *_variant_rows(["S", "M"], path="https://x/p/revolt-copy"),
    )
    assert client.get("/api/v1/bikes").json()["total"] == 2


def test_same_product_at_two_vendors_keeps_its_own_card(client, seed):
    seed(
        *_variant_rows(["S", "M"], vendor="Shop A"),
        *_variant_rows(["S", "M"], vendor="Shop B"),
    )
    body = client.get("/api/v1/bikes").json()
    assert body["total"] == 2, "comparing shops is the point of the site"
    assert {b["vendor_name"] for b in body["results"]} == {"Shop A", "Shop B"}


def test_size_filter_narrows_the_sizes_a_card_lists(client, seed):
    # Same rule as location_count under ?city=: a filtered feed answers
    # questions about the filtered catalogue.
    seed(*_variant_rows(["S", "M", "L"]))
    result = client.get("/api/v1/bikes", params={"size": "L"}).json()["results"][0]

    assert result["sizes"] == ["L"]


def test_unusable_sizes_produce_no_chips_at_all(client, seed):
    # "One Size" and "N/A" canonicalise to nothing. A chip reading N/A is worse
    # than no chip row.
    seed(*_variant_rows(["One Size", "N/A"]))
    body = client.get("/api/v1/bikes").json()

    assert body["total"] == 1
    assert body["results"][0]["sizes"] == []


def test_url_path_compiles_for_postgres_as_well_as_sqlite():
    """The prod dialect is the one CI never runs.

    Every test above proves the collapse on SQLite; production is Postgres, and
    _url_path is the one piece of this feature whose SQL differs between them.
    A broken Postgres branch does not fail a test, it 500s the main feed — so
    pin both strings. Compilation is as far as this can go without a server:
    that POSITION/SUBSTRING is valid Postgres is the standard's promise, not
    something asserted here.
    """
    from sqlalchemy import select as sa_select
    from sqlalchemy.dialects import postgresql, sqlite

    from api.main import _url_path
    from api.models import Bike

    def sql(dialect):
        return " ".join(
            str(sa_select(_url_path(Bike.product_url)).compile(dialect=dialect)).split()
        )

    assert sql(postgresql.dialect()) == (
        "SELECT CASE WHEN POSITION('?' IN bikes.product_url) > 0 "
        "THEN SUBSTRING(bikes.product_url FROM 1 FOR POSITION('?' IN bikes.product_url) - 1) "
        "ELSE bikes.product_url END AS url_path_1 FROM bikes"
    )
    assert sql(sqlite.dialect()) == (
        "SELECT CASE WHEN instr(bikes.product_url, '?') > 0 "
        "THEN substr(bikes.product_url, 1, instr(bikes.product_url, '?') - 1) "
        "ELSE bikes.product_url END AS url_path_1 FROM bikes"
    )


def test_url_path_sql_and_python_agree(client, seed):
    """The card is grouped in SQL, its size chips in Python. They must agree.

    If they drift, nothing raises — the cards just lose their size rows.
    """
    from api.main import _url_path_py

    urls = ["https://x/p?variant=1", "https://x/p", "https://x/p?a=1&b=2", "https://x/p?"]
    seed(*[
        make_bike(id=f"u{i}", product_url=u, frame_size=s)
        for i, (u, s) in enumerate(zip(urls, ["S", "M", "L", "XL"]))
    ])
    assert {_url_path_py(u) for u in urls} == {"https://x/p"}

    body = client.get("/api/v1/bikes").json()
    assert body["total"] == 1, "SQL agrees: every spelling is one product"
    assert body["results"][0]["sizes"] == ["S", "M", "L", "XL"], "and Python agrees"


def test_total_bikes_matches_the_size_collapsed_feed(client, seed):
    seed(*_variant_rows(["S", "M", "L", "XL"]))
    # The header's trust number and the feed must not disagree.
    assert client.get("/api/v1/meta/filters").json()["total_bikes"] == 1
    assert client.get("/api/v1/bikes").json()["total"] == 1


def test_sitemap_still_advertises_every_size(client, seed):
    # Deliberately divergent from the feed: /bikes/<id> for an L is a distinct
    # canonical page, and collapsing here would drop half the indexable site.
    seed(*_variant_rows(["S", "M", "L", "XL"]))

    assert client.get("/sitemap.xml").text.count("/bikes/") == 4
    assert client.get("/api/v1/bikes").json()["total"] == 1


def test_pagination_does_not_repeat_rows_across_pages(client, seed):
    # Every row ties on the sort key, which is the shape half the live feed has
    # (0% discount). Without a unique tiebreak the DB may order ties differently
    # per query, dropping and repeating rows between pages.
    seed(*[
        make_bike(id=f"tie-{i}", discount_percentage=0, price_original=None,
                  product_url=f"https://x/tie/{i}")
        for i in range(10)
    ])
    page1 = client.get("/api/v1/bikes", params={"limit": 5, "offset": 0}).json()["results"]
    page2 = client.get("/api/v1/bikes", params={"limit": 5, "offset": 5}).json()["results"]

    ids = [b["id"] for b in page1] + [b["id"] for b in page2]
    assert len(set(ids)) == 10


# --- the faceted filters endpoint -------------------------------------------

def _filters(client, **params):
    r = client.get("/api/v1/meta/filters", params=params)
    assert r.status_code == 200
    return r.json()


def test_facets_list_every_option(client, seed):
    seed(
        make_bike(id="a", category="Road", brand="Trek", vendor_name="Shop A",
                  city="Sydney", product_url="https://x/a"),
        make_bike(id="b", category="Gravel", brand="Giant", vendor_name="Shop B",
                  city="Melbourne", product_url="https://x/b"),
    )
    body = _filters(client)
    assert body["categories"] == ["Gravel", "Road"]
    assert body["brands"] == ["Giant", "Trek"]
    assert body["vendors"] == ["Shop A", "Shop B"]
    assert body["cities"] == ["Melbourne", "Sydney"]
    assert body["total_bikes"] == 2


def test_each_facet_excludes_itself(client, seed):
    """Picking Road must not reduce the category list to just Road — that traps
    the visitor with no way back. Every *other* facet does narrow."""
    seed(
        make_bike(id="a", category="Road", brand="Trek", product_url="https://x/a"),
        make_bike(id="b", category="Gravel", brand="Giant", product_url="https://x/b"),
    )
    body = _filters(client, category="Road")
    assert body["categories"] == ["Gravel", "Road"], "the category facet ignores itself"
    assert body["brands"] == ["Trek"], "other facets still narrow"


def test_facet_values_are_sorted(client, seed):
    seed(
        make_bike(id="a", brand="Zeta", product_url="https://x/a"),
        make_bike(id="b", brand="Alpha", product_url="https://x/b"),
        make_bike(id="c", brand="Mid", product_url="https://x/c"),
    )
    assert _filters(client)["brands"] == ["Alpha", "Mid", "Zeta"]


def test_facets_omit_nulls(client, seed):
    seed(
        make_bike(id="a", city=None, frame_material=None, drivetrain_groupset=None,
                  product_url="https://x/a"),
        make_bike(id="b", city="Perth", frame_material="Carbon",
                  drivetrain_groupset="Shimano 105", product_url="https://x/b"),
    )
    body = _filters(client)
    assert body["cities"] == ["Perth"]
    assert body["frame_materials"] == ["Carbon"]
    assert body["drivetrain_groupsets"] == ["Shimano 105"]


def test_ranges_and_price_filter_interaction(client, seed):
    seed(
        make_bike(id="a", price_sale=500.0, price_original=1000.0,
                  discount_percentage=50, product_url="https://x/a"),
        make_bike(id="b", price_sale=5000.0, price_original=6000.0,
                  discount_percentage=17, product_url="https://x/b"),
    )
    body = _filters(client)
    assert body["price_range"] == {"min": 500.0, "max": 5000.0}
    assert body["discount_range"] == {"min": 17, "max": 50}

    # price_range is the slider's *bounds*, so it deliberately ignores the
    # price filters themselves — shrinking it to the current selection would
    # leave no way to widen it again.
    narrowed = _filters(client, max_price=1000)
    assert narrowed["price_range"] == {"min": 500.0, "max": 5000.0}
    # And an out-of-range price must not empty the discrete facets either.
    assert narrowed["categories"] == body["categories"]


def test_out_of_stock_is_excluded_from_every_facet(client, seed):
    seed(
        make_bike(id="a", brand="Trek", in_stock=True, product_url="https://x/a"),
        make_bike(id="b", brand="Gone", in_stock=False, product_url="https://x/b"),
    )
    body = _filters(client)
    assert body["brands"] == ["Trek"]
    assert body["total_bikes"] == 1


def test_filters_endpoint_stays_within_its_round_trip_budget(client, seed, sync_engine):
    """The point of the UNION ALL: this endpoint is round-trip bound.

    It used to issue eleven sequential statements and took ~0.8s in production
    against a remote Postgres, where /bikes took ~0.28s over the same table.
    Adding a separate query per facet is the easy way to put that back, so the
    budget is asserted rather than left as a comment.

    Five, not four: the seven facets share one UNION ALL, and the discount range
    and price range are one query each, but the chain-collapsed total is a
    GROUP BY count and cannot ride along with the min/max aggregates.
    """
    from sqlalchemy import event

    seed(make_bike(id="a"))
    statements = []

    engine = main_module.get_engine().sync_engine

    @event.listens_for(engine, "before_cursor_execute")
    def _record(conn, cursor, statement, *args):
        statements.append(statement)

    try:
        assert client.get("/api/v1/meta/filters").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert len(statements) <= 5, (
        f"{len(statements)} round trips; the seven facets should share one "
        f"statement:\n" + "\n".join(" ".join(s.split())[:90] for s in statements)
    )


# --- /api/v1/meta/market ------------------------------------------------------


def _market(client):
    r = client.get("/api/v1/meta/market")
    assert r.status_code == 200
    return r


def _chart(body, name):
    return [p for p in body["points"] if p["chart"] == name]


def test_market_empty_db(client):
    r = _market(client)
    body = r.json()
    assert body["total_listings"] == 0
    assert body["points"] == []
    assert body["coverage"] == {"frame_material": 0, "drivetrain_groupset": 0}
    assert r.headers["cache-control"] == "max-age=3600"


def test_market_counts_cards_not_rows(client, seed):
    """Two sizes of one product are one card, so they must count once.

    The header's "N bikes" and these charts read the same catalogue; if they
    disagree the page is visibly wrong on its own first line.
    """
    seed(
        make_bike(id="a", frame_size="M", price_sale=1500.0,
                  product_url="https://shop.example.com/p/1?variant=m"),
        make_bike(id="b", frame_size="L", price_sale=1600.0,
                  product_url="https://shop.example.com/p/1?variant=l"),
    )
    body = _market(client).json()
    assert body["total_listings"] == 1
    assert sum(p["n"] for p in _chart(body, "cell_totals")) == 1

    # ...and it is the fronting (cheapest) variant that was kept, so the
    # listing lands in the band its card advertises.
    assert _chart(body, "cell_totals")[0]["bucket"] == "$1–2k"

    filters = client.get("/api/v1/meta/filters").json()
    assert body["total_listings"] == filters["total_bikes"]


def test_market_excludes_out_of_stock(client, seed):
    seed(
        make_bike(id="a", product_url="https://shop.example.com/p/1"),
        make_bike(id="b", in_stock=False, product_url="https://shop.example.com/p/2"),
    )
    assert _market(client).json()["total_listings"] == 1


def test_market_coverage_counts_only_enriched_listings(client, seed):
    """A null attribute drops out of its chart but still counts as a listing."""
    seed(
        make_bike(id="a", frame_material="Carbon", drivetrain_groupset="Shimano 105",
                  product_url="https://shop.example.com/p/1"),
        make_bike(id="b", frame_material=None, drivetrain_groupset=None,
                  product_url="https://shop.example.com/p/2"),
        make_bike(id="c", frame_material="Steel", drivetrain_groupset=None,
                  product_url="https://shop.example.com/p/3"),
    )
    body = _market(client).json()
    assert body["total_listings"] == 3
    assert body["coverage"] == {"frame_material": 2, "drivetrain_groupset": 1}
    assert sum(p["n"] for p in _chart(body, "material_by_band")) == 2
    assert {p["series"] for p in _chart(body, "material_by_band")} == {"Carbon", "Steel"}


@pytest.mark.parametrize(
    "price,band",
    [
        (999.0, "Under $1k"),
        (1000.0, "$1–2k"),
        (1999.99, "$1–2k"),
        (2000.0, "$2–3k"),
        (12000.0, "$12k+"),
        (167999.0, "$12k+"),
    ],
)
def test_market_price_band_boundaries(client, seed, price, band):
    """Bands are half-open: the upper bound belongs to the next band up."""
    seed(make_bike(price_sale=price, price_original=price, discount_percentage=0))
    body = _market(client).json()
    assert _chart(body, "cell_totals")[0]["bucket"] == band


@pytest.mark.parametrize(
    "discount,bucket",
    [(1, "1–9%"), (9, "1–9%"), (10, "10–19%"), (60, "60%+"), (69, "60%+")],
)
def test_market_discount_bin_boundaries(client, seed, discount, bucket):
    seed(make_bike(discount_percentage=discount))
    body = _market(client).json()
    assert [p["bucket"] for p in _chart(body, "discount_hist")] == [bucket]


def test_market_discount_charts_ignore_full_price_listings(client, seed):
    """Full-price listings are the heatmap's denominator, never its depth."""
    seed(
        make_bike(id="a", discount_percentage=0, price_sale=1500.0,
                  price_original=1500.0, product_url="https://shop.example.com/p/1"),
        make_bike(id="b", discount_percentage=40, price_sale=1200.0,
                  product_url="https://shop.example.com/p/2"),
    )
    body = _market(client).json()
    assert _chart(body, "discount_hist") == [
        {"chart": "discount_hist", "bucket": "40–49%", "bucket_rank": 4,
         "series": "all", "n": 1, "value": None}
    ]
    depth = _chart(body, "discount_depth")
    assert [(p["n"], p["value"]) for p in depth] == [(1, 40.0)]
    # Both listings are in the same cell, so the denominator sees both.
    assert sum(p["n"] for p in _chart(body, "cell_totals")) == 2


def test_market_median_price_is_per_category(client, seed):
    seed(
        make_bike(id="a", category="Road", price_sale=1600.0,
                  product_url="https://shop.example.com/p/1"),
        make_bike(id="b", category="Road", price_sale=1900.0,
                  product_url="https://shop.example.com/p/2"),
        make_bike(id="c", category="Gravel", price_sale=4200.0,
                  product_url="https://shop.example.com/p/3"),
    )
    body = _market(client).json()
    medians = {p["series"]: p["value"] for p in _chart(body, "median_price")}
    assert set(medians) == {"Road", "Gravel"}
    # Interpolated within the bin, so assert the bin rather than an exact dollar.
    assert 1500 <= medians["Road"] <= 2000
    assert 4000 <= medians["Gravel"] <= 5000


def test_market_brands_are_ranked_and_capped(client, seed):
    bikes = []
    for i in range(30):
        for j in range(i + 1):  # brand i gets i+1 listings
            bikes.append(make_bike(
                id=f"b{i}-{j}", brand=f"Brand{i:02d}", model_name=f"M{i}-{j}",
                product_url=f"https://shop.example.com/p/{i}-{j}",
            ))
    seed(*bikes)
    brands = _chart(_market(client).json(), "brands")
    assert len(brands) == 25  # the ~165-brand tail is not shipped
    assert brands[0]["series"] == "Brand29"
    assert [p["n"] for p in brands] == sorted((p["n"] for p in brands), reverse=True)


def test_market_points_are_emitted_in_render_order(client, seed):
    """The client renders in encounter order and keeps no ordering constants."""
    seed(
        make_bike(id="a", category="Road", price_sale=9000.0,
                  product_url="https://shop.example.com/p/1"),
        make_bike(id="b", category="Commuter", price_sale=800.0,
                  product_url="https://shop.example.com/p/2"),
        make_bike(id="c", category="Gravel", price_sale=800.0,
                  product_url="https://shop.example.com/p/3"),
    )
    body = _market(client).json()
    for name in ("cell_totals", "price_hist", "material_by_band"):
        ranks = [p["bucket_rank"] for p in _chart(body, name)]
        assert ranks == sorted(ranks), name
    # Within one bucket, categories follow _CATEGORY_ORDER, not the alphabet.
    first_band = [p["series"] for p in _chart(body, "cell_totals")
                  if p["bucket"] == "Under $1k"]
    assert first_band == ["Commuter", "Gravel"]


def test_market_endpoint_issues_one_query(client, seed, sync_engine):
    """Eight aggregations, one round trip.

    Same reasoning as the filters budget above: this endpoint is round-trip
    bound against a remote Postgres, and adding a chart is the easy way to
    quietly add a query. The UNION ALL is the whole design, so assert it.
    """
    from sqlalchemy import event

    seed(make_bike(id="a", frame_material="Carbon", drivetrain_groupset="Shimano 105"))
    statements = []

    engine = main_module.get_engine().sync_engine

    @event.listens_for(engine, "before_cursor_execute")
    def _record(conn, cursor, statement, *args):
        statements.append(statement)

    try:
        assert client.get("/api/v1/meta/market").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert len(statements) == 1, (
        f"{len(statements)} round trips; every chart should ride the one "
        f"UNION ALL:\n" + "\n".join(" ".join(s.split())[:90] for s in statements)
    )
