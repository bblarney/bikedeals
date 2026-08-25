"""Endpoint tests for the BikeGrid API (hardened contract)."""
from datetime import datetime, timedelta, timezone

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
    # One entry per size (cheapest), current size included.
    assert [(v["frame_size"], v["bike_id"]) for v in body["variants"]] == [
        ("L", "l1"), ("M", "m1"),
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

    assert len(statements) <= 4, (
        f"{len(statements)} round trips; the seven facets should share one "
        f"statement:\n" + "\n".join(" ".join(s.split())[:90] for s in statements)
    )
