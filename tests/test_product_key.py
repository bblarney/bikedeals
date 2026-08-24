"""Cross-shop product identity.

`product_key` decides which listings are "the same bike at another shop". Get it
too loose and the site quotes one product's price against another's; too tight
and genuine comparisons disappear. Both directions are covered here.
"""
import importlib.util
from pathlib import Path

import pytest

from scrapers.models import _canonical_brand, make_product_key

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations" / "versions" / "f6a3c81b4d92_add_product_key.py"
)


def test_no_sku_means_no_key():
    # 13% of live listings publish no SKU. They must stay unmatched rather than
    # collapsing into a shared "brand:" bucket.
    assert make_product_key("Trek", None) is None
    assert make_product_key("Trek", "") is None
    assert make_product_key("Trek", "   ") is None


def test_sku_is_scoped_by_brand():
    # The live collision: one Lightspeed counter, two unrelated bikes.
    assert make_product_key("Jamis", "210000015200") != make_product_key("Amflow", "210000015200")


def test_brand_casing_and_punctuation_do_not_split_a_product():
    assert make_product_key("GIANT", "1073001320") == make_product_key("Giant", "1073001320")
    assert make_product_key("Rocky Mountain", "A1") == make_product_key("rocky-mountain", "A1")


@pytest.mark.parametrize(
    "a, b",
    [
        ("Progear", "Progear Bikes"),
        ("Specialized", "SPECIALIZED BICYCLES"),
        ("Kona", "Kona Bicycles"),
        ("Norco", "Norco Bikes"),
        ("Eastern", "Eastern BMX"),
        ("Santa Cruz", "Santa Cruz Bicycles"),
    ],
)
def test_corporate_suffixes_are_the_same_brand(a, b):
    assert make_product_key(a, "X") == make_product_key(b, "X")


@pytest.mark.parametrize(
    "a, b",
    [
        # A shop name that merely contains a brand name is not that brand.
        ("Liv", "Live Life Cycling"),
        # A sub-brand is its own brand.
        ("Juliana", "Santa Cruz Juliana"),
        # Giant's SKUs appear on Liv bikes; they are different products.
        ("Giant", "Liv"),
        # A distributor is not the manufacturer.
        ("Merida", "Advance Traders"),
    ],
)
def test_similar_but_distinct_brands_stay_separate(a, b):
    assert make_product_key(a, "X") != make_product_key(b, "X")


def test_a_brand_is_never_stripped_to_a_stub():
    # Without the minimum-stem guard, a brand literally named "Cycles" would
    # normalise to the empty string and collide with every other such brand.
    assert _canonical_brand("Cycles") == "cycles"
    assert _canonical_brand("Bike") == "bike"


def test_migration_backfill_matches_the_scraper():
    """The migration carries a frozen copy of the normalisation on purpose.

    If the two drift, the backfill keys existing rows differently from the ones
    the scraper writes and every product silently splits in two — with no error
    anywhere. This is the only thing that catches that.
    """
    spec = importlib.util.spec_from_file_location("_mig", MIGRATION)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    samples = [
        "Trek", "Giant", "GIANT", "Progear Bikes", "SPECIALIZED BICYCLES",
        "Live Life Cycling", "Liv", "Cycles", "Eastern BMX", "Santa Cruz Juliana",
        "Rocky Mountain", "Norco Bikes", "Forbidden Bike Co", "Reid Cycles",
    ]
    mismatched = [s for s in samples if mig._canonical_brand(s) != _canonical_brand(s)]
    assert not mismatched, f"migration normalisation drifted from the scraper: {mismatched}"
