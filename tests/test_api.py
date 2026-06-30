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
