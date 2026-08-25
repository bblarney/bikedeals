"""Endpoint tests for the BikeGrid API (hardened contract)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

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


def test_collapse_keeps_distinct_products_and_sizes_apart(client, seed):
    seed(
        *_chain_rows(["Sydney", "Melbourne"], product_url="https://x/a", frame_size="M"),
        *_chain_rows(["Sydney", "Melbourne"], product_url="https://x/a", frame_size="L"),
        *_chain_rows(["Sydney", "Melbourne"], product_url="https://x/b", frame_size="M"),
    )
    body = client.get("/api/v1/bikes").json()

    assert body["total"] == 3, "two sizes of one product plus a second product"
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
