"""Unit tests for the price change-event decision logic.

The full upsert path uses Postgres-only ``on_conflict_do_update`` (not runnable
against the SQLite dev DB), so the testable core — *which* records become
events — is extracted into ``price_event_rows``.
"""
from datetime import datetime, timezone

from scrapers.db import price_event_rows
from scrapers.models import BikeRecord


def make_record(id="bike-1", price_sale=1500.0, price_original=2000.0):
    now = datetime.now(timezone.utc)
    return BikeRecord(
        id=id,
        vendor_name="Test Cycles",
        city="Sydney",
        brand="Trek",
        model_name="Domane SL5",
        category="Road",
        frame_size="M",
        price_original=price_original,
        price_sale=price_sale,
        discount_percentage=25,
        in_stock=True,
        product_url="https://shop.example.com/p/1",
        image_url=None,
        scraped_at=now,
        last_seen_at=now,
    )


def test_new_listing_seeds_an_event():
    rows = price_event_rows([make_record()], prior={})
    assert len(rows) == 1
    assert rows[0]["bike_id"] == "bike-1"
    assert rows[0]["price_sale"] == 1500.0


def test_unchanged_price_writes_no_event():
    rows = price_event_rows(
        [make_record(price_sale=1500.0)], prior={"bike-1": (1500.0, 2000.0)}
    )
    assert rows == []


def test_changed_price_writes_an_event():
    rows = price_event_rows(
        [make_record(price_sale=1300.0)], prior={"bike-1": (1500.0, 2000.0)}
    )
    assert len(rows) == 1
    assert rows[0]["price_sale"] == 1300.0


def test_changed_rrp_writes_an_event_even_when_sale_holds():
    # Shop bumps the struck-through RRP while the sale price stays put. The
    # chart draws the RRP line, so this must still be recorded.
    rows = price_event_rows(
        [make_record(price_sale=1500.0, price_original=2500.0)],
        prior={"bike-1": (1500.0, 2000.0)},
    )
    assert len(rows) == 1
    assert rows[0]["price_original"] == 2500.0


def test_rrp_appearing_is_a_change():
    # A listing goes on sale: RRP transitions from None to a value.
    rows = price_event_rows(
        [make_record(price_sale=1500.0, price_original=2000.0)],
        prior={"bike-1": (1500.0, None)},
    )
    assert len(rows) == 1


def test_rrp_disappearing_is_a_change():
    # A sale ends: RRP transitions from a value back to None.
    rows = price_event_rows(
        [make_record(price_sale=1500.0, price_original=None)],
        prior={"bike-1": (1500.0, 2000.0)},
    )
    assert len(rows) == 1


def test_no_rrp_both_sides_writes_no_event():
    # Never-discounted listing, unchanged sale price: no event.
    rows = price_event_rows(
        [make_record(price_sale=1500.0, price_original=None)],
        prior={"bike-1": (1500.0, None)},
    )
    assert rows == []


def test_sub_cent_wobble_is_not_a_change():
    # Float representation noise must not register as a price change.
    rows = price_event_rows(
        [make_record(price_sale=1500.004, price_original=2000.004)],
        prior={"bike-1": (1500.0, 2000.0)},
    )
    assert rows == []


def test_mixed_batch_only_emits_new_and_changed():
    records = [
        make_record(id="new"),                       # new -> event
        make_record(id="same", price_sale=999.0),    # unchanged -> no event
        make_record(id="dropped", price_sale=800.0), # changed -> event
    ]
    prior = {"same": (999.0, 2000.0), "dropped": (1000.0, 2000.0)}
    ids = {r["bike_id"] for r in price_event_rows(records, prior)}
    assert ids == {"new", "dropped"}
