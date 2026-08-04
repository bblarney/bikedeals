"""Unit tests for the WooCommerce Store API pipeline's pure helpers."""
from datetime import datetime, timezone

import pytest

from scrapers.models import VendorConfig
from scrapers.pipelines.woocommerce_api import (
    _build_records,
    _clean_text,
    _frame_sizes,
    _is_electric_slug,
    _known_brands,
    _price,
    _resolve_brand,
)

NOW = datetime(2026, 8, 4, tzinfo=timezone.utc)


def make_config(**overrides) -> VendorConfig:
    base = dict(
        vendor_name="Test Shop",
        city="Perth",
        base_url="https://shop.example",
        pipeline="woocommerce_api",
        collections=["bikes"],
        category_map={
            "electric-bikes": "E-Bike",
            "mountain-bikes": "Mountain",
            "road-bikes": "Road",
            "talon": "Mountain",
        },
    )
    base.update(overrides)
    return VendorConfig(**base)


def make_product(**overrides) -> dict:
    base = {
        "id": 1,
        "name": "Giant Talon 1",
        "permalink": "https://shop.example/product/giant-talon-1/",
        "prices": {
            "price": "129900",
            "regular_price": "129900",
            "sale_price": "129900",
            "currency_minor_unit": 2,
        },
        "is_in_stock": True,
        "categories": [{"slug": "mountain-bikes"}],
        "brands": [{"name": "Giant"}],
        "images": [{"src": "https://shop.example/talon.jpg"}],
        "attributes": [],
    }
    base.update(overrides)
    return base


# --- _clean_text --------------------------------------------------------------

def test_clean_text_unescapes_entities_and_collapses_whitespace():
    assert _clean_text("Giant Revolt &#8211;  Raw   Carbon") == "Giant Revolt – Raw Carbon"


def test_clean_text_handles_none():
    assert _clean_text(None) == ""


# --- _price -------------------------------------------------------------------

def test_price_scales_by_minor_unit():
    # 1399900 with 2 minor digits is $13,999.00, not $1,399,900.
    assert _price({"price": "1399900", "currency_minor_unit": 2}, "price") == 13999.00


def test_price_defaults_to_two_minor_digits():
    assert _price({"price": "89900"}, "price") == 899.00


def test_price_respects_zero_decimal_currencies():
    assert _price({"price": "1500", "currency_minor_unit": 0}, "price") == 1500.0


@pytest.mark.parametrize("prices", [{}, {"price": None}, {"price": ""}, {"price": "abc"}])
def test_price_missing_or_unparseable(prices):
    assert _price(prices, "price") is None


# --- _frame_sizes -------------------------------------------------------------

def test_frame_sizes_strips_wheel_qualifiers():
    product = make_product(attributes=[{
        "name": "Frame Size:",
        "has_variations": True,
        "terms": [
            {"name": "Extra Small (F/R 27.5\")"},
            {"name": "Small (F/R 29\")"},
            {"name": "Medium - 29"},
            {"name": "Extra Small (F 29\"/R 27.5\")"},
        ],
    }])
    # The two Extra Small terms collapse to one once the wheel spec is stripped.
    assert _frame_sizes(product) == ["Extra Small", "Small", "Medium"]


def test_frame_sizes_ignores_non_variation_attributes():
    product = make_product(attributes=[
        {"name": "Colour", "has_variations": True, "terms": [{"name": "Red"}]},
        {"name": "Frame Size:", "has_variations": True, "terms": [{"name": "Large"}]},
    ])
    assert _frame_sizes(product) == ["Large"]


def test_frame_sizes_ignores_size_attribute_without_variations():
    product = make_product(attributes=[
        {"name": "Frame Size:", "has_variations": False, "terms": [{"name": "Large"}]},
    ])
    assert _frame_sizes(product) == ["One Size"]


def test_frame_sizes_defaults_for_simple_products():
    assert _frame_sizes(make_product(attributes=[])) == ["One Size"]


# --- brand resolution ---------------------------------------------------------

def test_known_brands_are_longest_first():
    products = {
        1: make_product(brands=[{"name": "Liv"}]),
        2: make_product(id=2, brands=[{"name": "Giant"}]),
        3: make_product(id=3, brands=[]),
    }
    assert _known_brands(products) == ["Giant", "Liv"]


def test_resolve_brand_uses_the_brands_field():
    assert _resolve_brand(make_product(), ["Giant"], make_config()) == "Giant"


def test_resolve_brand_falls_back_to_a_brand_named_in_the_title():
    product = make_product(brands=[], name="Giant AnyTour X E+ 3 2027 – Good Grey")
    assert _resolve_brand(product, ["Giant", "Liv"], make_config()) == "Giant"


def test_resolve_brand_falls_back_to_vendor_name_when_nothing_matches():
    product = make_product(brands=[], name="Mystery Bike 3000")
    assert _resolve_brand(product, ["Giant"], make_config()) == "Test Shop"


def test_resolve_brand_applies_brand_map():
    config = make_config(brand_map={"Giant Bicycles": "Giant"})
    product = make_product(brands=[{"name": "Giant Bicycles"}])
    assert _resolve_brand(product, [], config) == "Giant"


# --- _build_records -----------------------------------------------------------

def test_build_records_emits_one_row_per_size():
    product = make_product(attributes=[{
        "name": "Frame Size:",
        "has_variations": True,
        "terms": [{"name": "Small"}, {"name": "Medium"}, {"name": "Large"}],
    }])
    bikes, invalid, skipped = _build_records(make_config(), {1: product}, NOW)
    assert [b.frame_size for b in bikes] == ["Small", "Medium", "Large"]
    assert (invalid, skipped) == (0, 0)
    assert {b.id for b in bikes} == {b.id for b in bikes} and len({b.id for b in bikes}) == 3


def test_build_records_computes_the_discount():
    product = make_product(prices={
        "price": "71900", "regular_price": "89900", "sale_price": "71900",
        "currency_minor_unit": 2,
    })
    bikes, _, _ = _build_records(make_config(), {1: product}, NOW)
    assert (bikes[0].price_sale, bikes[0].price_original) == (719.0, 899.0)
    assert bikes[0].discount_percentage == 20


def test_build_records_treats_equal_prices_as_no_discount():
    bikes, _, _ = _build_records(make_config(), {1: make_product()}, NOW)
    assert bikes[0].price_original is None
    assert bikes[0].discount_percentage == 0


def test_build_records_prefers_the_electric_category_over_mountain():
    # An e-MTB is filed under both; the API's ordering must not decide.
    product = make_product(
        name="Giant Talon E+",
        categories=[{"slug": "mountain-bikes"}, {"slug": "electric-bikes"}],
    )
    bikes, _, _ = _build_records(make_config(), {1: product}, NOW)
    assert bikes[0].category == "E-Bike"


@pytest.mark.parametrize(
    "slug, electric",
    [
        ("electric-bikes", True),
        ("e-bikes", True),
        # Unhyphenated spellings — Cycle World files e-MTBs under "mtb-ebikes"
        # with no "electric" or "e-bike" anywhere, and missing them dropped the
        # electric-first ordering that stops the mountain category winning.
        ("ebikes", True),
        ("mtb-ebikes", True),
        ("dual-suspension-enduro-ebikes", True),
        ("mountain-bikes", False),
        ("road-bikes", False),
        ("bikes", False),
    ],
)
def test_is_electric_slug(slug, electric):
    assert _is_electric_slug(slug) is electric


def test_build_records_prefers_an_unhyphenated_ebike_category():
    product = make_product(
        name="Merida eOne-Sixty 500",
        categories=[{"slug": "mtb-bikes"}, {"slug": "mtb-ebikes"}],
    )
    config = make_config(category_map={"mtb-bikes": "Mountain", "mtb-ebikes": "E-Bike"})
    bikes, _, _ = _build_records(config, {1: product}, NOW)
    assert bikes[0].category == "E-Bike"


def test_build_records_falls_back_to_the_model_name_for_category():
    product = make_product(name="Giant Talon 1", categories=[{"slug": "clearance"}])
    bikes, _, _ = _build_records(make_config(), {1: product}, NOW)
    assert bikes[0].category == "Mountain"


def test_build_records_skips_uncategorisable_products():
    product = make_product(name="Gift Voucher", categories=[{"slug": "vouchers"}])
    bikes, invalid, skipped = _build_records(make_config(), {1: product}, NOW)
    assert (bikes, invalid, skipped) == ([], 0, 1)


def test_build_records_skips_products_without_a_price():
    product = make_product(prices={"price": "0", "currency_minor_unit": 2})
    bikes, _, _ = _build_records(make_config(), {1: product}, NOW)
    assert bikes == []


def test_build_records_skips_products_without_a_permalink():
    bikes, _, _ = _build_records(make_config(), {1: make_product(permalink="")}, NOW)
    assert bikes == []
