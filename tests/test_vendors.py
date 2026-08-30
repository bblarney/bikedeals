"""Endpoint tests for /api/v1/vendors, which backs the shops tab.

The case that matters is the collapse. A chain publishes one national catalogue
and gets one bikes row per city, so counting raw rows would report 99 Bikes at
eight times its real range on a page whose whole job is comparing shops.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.models import ScrapeLog
from tests.conftest import make_bike


def vendors_by_name(client):
    r = client.get("/api/v1/vendors")
    assert r.status_code == 200
    return {v["vendor_name"]: v for v in r.json()["vendors"]}


def test_vendors_empty(client):
    r = client.get("/api/v1/vendors")
    assert r.status_code == 200
    assert r.json() == {"vendors": []}
    assert r.headers["cache-control"] == "max-age=300"


def test_vendors_counts_listings_and_discounts(client, seed):
    seed(
        make_bike(id="a", vendor_name="Shop A", discount_percentage=40,
                  product_url="https://a/1"),
        make_bike(id="b", vendor_name="Shop A", discount_percentage=0,
                  model_name="Other", product_url="https://a/2"),
        make_bike(id="c", vendor_name="Shop B", discount_percentage=10,
                  product_url="https://b/1"),
    )
    by_name = vendors_by_name(client)
    assert by_name["Shop A"] == {
        "vendor_name": "Shop A", "listings": 2, "on_sale": 1,
        "deepest_cut": 40, "last_success_at": None,
    }
    assert by_name["Shop B"]["listings"] == 1
    assert by_name["Shop B"]["deepest_cut"] == 10


def test_vendors_collapses_a_chains_storefronts(client, seed):
    # One product, one price, listed in three cities: the shape make_bike_id
    # produces for a vendor with a `cities:` list. It is one listing, not three.
    seed(*[
        make_bike(id=f"chain-{city}", vendor_name="Chain", city=city,
                  product_url="https://chain/p1", discount_percentage=30)
        for city in ("Sydney", "Melbourne", "Brisbane")
    ])
    assert vendors_by_name(client)["Chain"] == {
        "vendor_name": "Chain", "listings": 1, "on_sale": 1,
        "deepest_cut": 30, "last_success_at": None,
    }


def test_vendors_collapses_size_variants(client, seed):
    # The same bike in three sizes is one listing on the feed, so it is one
    # listing here. Distinct ids and urls, same brand/model/url path.
    seed(*[
        make_bike(id=f"size-{size}", vendor_name="Sizes", frame_size=size,
                  product_url=f"https://s/p1?variant={i}", discount_percentage=20)
        for i, size in enumerate(("S", "M", "L"))
    ])
    assert vendors_by_name(client)["Sizes"]["listings"] == 1


def test_vendors_excludes_out_of_stock(client, seed):
    seed(
        make_bike(id="in", vendor_name="Shop", product_url="https://s/1"),
        make_bike(id="out", vendor_name="Shop", in_stock=False,
                  model_name="Gone", product_url="https://s/2"),
    )
    assert vendors_by_name(client)["Shop"]["listings"] == 1


def test_vendors_keeps_a_shop_with_nothing_discounted(client, seed):
    # Roughly a fifth of shops look like this on a given day. The shops page
    # lists every shop, so a full-price shop must not vanish from the payload.
    seed(make_bike(id="full", vendor_name="Full Price", discount_percentage=0))
    row = vendors_by_name(client)["Full Price"]
    assert row["listings"] == 1
    assert row["on_sale"] == 0
    assert row["deepest_cut"] == 0


def test_vendors_reports_last_successful_scrape(client, seed, sync_engine):
    seed(make_bike(vendor_name="Logged"))
    when = datetime(2026, 8, 29, 13, 36, tzinfo=timezone.utc)
    with Session(sync_engine) as s:
        s.add(ScrapeLog(vendor_name="Logged", run_at=when, status="ok",
                        bikes_upserted=1, last_success_at=when))
        s.commit()
    assert vendors_by_name(client)["Logged"]["last_success_at"].startswith("2026-08-29T13:36")


def test_vendors_includes_a_shop_with_no_scrape_log_row(client, seed):
    # LEFT join, not INNER: a vendor with stock but no log row still appears,
    # just without a checked-at time.
    seed(make_bike(vendor_name="Unlogged"))
    assert vendors_by_name(client)["Unlogged"]["last_success_at"] is None


def test_vendors_scrape_log_for_another_vendor_does_not_leak(client, seed, sync_engine):
    seed(make_bike(vendor_name="Mine"))
    with Session(sync_engine) as s:
        s.add(ScrapeLog(vendor_name="Theirs", run_at=datetime.now(timezone.utc),
                        status="ok", last_success_at=datetime.now(timezone.utc)))
        s.commit()
    assert vendors_by_name(client)["Mine"]["last_success_at"] is None


def test_vendors_listing_count_matches_the_feed(client, seed):
    # The two numbers are shown side by side on the site, so they must agree:
    # a chain product in three cities plus a second product at the same shop.
    seed(
        *[make_bike(id=f"c-{c}", vendor_name="Shop", city=c,
                    product_url="https://s/p1") for c in ("Sydney", "Perth", "Hobart")],
        make_bike(id="solo", vendor_name="Shop", model_name="Solo",
                  product_url="https://s/p2"),
    )
    feed_total = client.get("/api/v1/bikes", params={"vendor": "Shop"}).json()["total"]
    assert vendors_by_name(client)["Shop"]["listings"] == feed_total == 2


def test_vendors_sorted_by_name(client, seed):
    seed(
        make_bike(id="z", vendor_name="Zed Cycles", product_url="https://z/1"),
        make_bike(id="a", vendor_name="Alpha Bikes", product_url="https://a/1"),
    )
    names = [v["vendor_name"] for v in client.get("/api/v1/vendors").json()["vendors"]]
    assert names == sorted(names)


def test_sitemap_lists_the_shops_index_and_shop_pages(client):
    body = client.get("/sitemap.xml").text
    assert "<loc>https://bikegrid.com.au/shops</loc>" in body
    # Derived from the registry with the same slug rule the frontend uses.
    assert "<loc>https://bikegrid.com.au/shops/99-bikes</loc>" in body
