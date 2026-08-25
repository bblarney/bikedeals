"""Tests for the single-vendor scrape tester's vendor resolution and verdict."""
from types import SimpleNamespace

import pytest

from scrapers.models import VendorConfig
from scrapers.run import QUARANTINE_INVALID_RATIO
from scrapers.scrape_check import _verdict, find_vendor


def _cfg(name):
    return VendorConfig(
        vendor_name=name, city="X", base_url="https://x",
        pipeline="shopify", category_map={},
    )


REGISTRY = [_cfg("Hendry's"), _cfg("Crooze"), _cfg("Drift Bikes"), _cfg("Bike Society")]


# --- find_vendor --------------------------------------------------------------

@pytest.mark.parametrize("query", ["Hendry's", "hendrys", "HENDRYS", "Hendrys"])
def test_find_vendor_normalizes_name(query):
    assert find_vendor(REGISTRY, query).vendor_name == "Hendry's"


def test_find_vendor_unique_substring():
    assert find_vendor(REGISTRY, "drift").vendor_name == "Drift Bikes"


def test_find_vendor_ambiguous_raises():
    reg = [_cfg("Bike Society"), _cfg("Bike Shed")]
    with pytest.raises(LookupError, match="ambiguous"):
        find_vendor(reg, "bike")


def test_find_vendor_no_match_lists_options():
    with pytest.raises(LookupError, match="No vendor matches"):
        find_vendor(REGISTRY, "nonexistent-shop")


# --- _verdict mirrors production ----------------------------------------------

def _result(bikes=0, invalid=0, error=None, non_bikes=0):
    # _verdict only reads len(bikes), invalid_count, non_bike_count and error.
    return SimpleNamespace(
        bikes=[None] * bikes,
        invalid_count=invalid,
        non_bike_count=non_bikes,
        non_bike_reasons={},
        error=error,
    )


def test_verdict_pass():
    label, code = _verdict(_result(bikes=10))
    assert code == 0 and label == "PASS"


def test_verdict_error_fails():
    _, code = _verdict(_result(error="boom"))
    assert code == 1


def test_verdict_zero_bikes_fails():
    _, code = _verdict(_result(bikes=0))
    assert code == 1


def test_verdict_high_invalid_ratio_fails():
    # 2 valid + 98 invalid = 98% invalid, well over the threshold.
    _, code = _verdict(_result(bikes=2, invalid=98))
    assert code == 1


def test_verdict_low_invalid_ratio_passes():
    assert QUARANTINE_INVALID_RATIO >= 0.02  # guard the assumption below
    # 99 valid + 1 invalid = 1% invalid, under the threshold.
    _, code = _verdict(_result(bikes=99, invalid=1))
    assert code == 0


def test_dropped_non_bikes_do_not_push_a_vendor_into_quarantine():
    """The gate runs before the verdict, so its rejects stay in the denominator.

    A shop listing 40 accessories alongside 60 bikes, with 2 genuine parse
    failures, is a 2% invalid rate — not 3.2%, and nowhere near quarantine.
    Dropping the accessories must not be what quarantines the vendor.
    """
    label, code = _verdict(_result(bikes=60, invalid=2, non_bikes=40))
    assert code == 0, label
