# -*- coding: utf-8 -*-
"""One brand, one name.

Every brand string here appeared in the live 246-entry brand facet, and every
recovery case is a real listing.
"""
from datetime import datetime, timezone

import pytest

from scrapers.brands import brand_from_model_name, canonical_brand_name, fold_brand
from scrapers.models import BikeRecord, make_product_key


# --- the four kinds of duplicate the facet had ------------------------------

@pytest.mark.parametrize(
    "variants, expected",
    [
        # Casing.
        (["FELT", "Felt"], "Felt"),
        (["GT", "Gt"], "GT"),
        (["MONGOOSE", "Mongoose"], "Mongoose"),
        (["JAMIS", "Jamis"], "Jamis"),
        # Corporate suffixes.
        (["Norco", "Norco Bicycles", "Norco Bikes"], "Norco"),
        (["Reid", "Reid Cycles"], "Reid"),
        (["Surly", "SURLY", "Surly Bikes"], "Surly"),
        (["Fuji", "Fuji Bikes"], "Fuji"),
        (["Specialized", "SPECIALIZED BICYCLES"], "Specialized"),
        (["Santa Cruz", "Santa Cruz Bicycles"], "Santa Cruz"),
        (["Icon", "ICON", "Icon Bikes"], "Icon"),
        (["Eastern", "EASTERN", "Eastern BMX"], "Eastern"),
        # Accents.
        (["Cervelo", "CERVELO", "Cervélo"], "Cervélo"),
        (["Riese and Muller", "Riese and Müller", "RIESE + MULLER"], "Riese & Müller"),
        # Punctuation and wording.
        (["X-LAB", "X-Lab", "X-lab", "XLAB"], "X-Lab"),
        (["AMPD BROS", "Ampd Bros", "AMPD BROTHERS"], "Ampd Bros"),
        (["ET Cycle", "ET-Cycles", "ET.CYCLE"], "ET Cycle"),
        (["Forbidden", "Forbidden Bike Co", "FORBIDDEN BIKE CO."], "Forbidden"),
        (["XDS", "XDS Bikes"], "XDS"),
        (["Liv", "LIV CYCLING"], "Liv"),
    ],
)
def test_every_spelling_collapses_to_one_name(variants, expected):
    assert {canonical_brand_name(v) for v in variants} == {expected}


def test_unknown_brand_is_left_exactly_as_scraped():
    """Normalising must never invent a brand. An unrecognised one is far less
    damaging than a wrong one."""
    for brand in ("Blitzen Bikes", "Wombat", "Hokus", "Lagads"):
        assert canonical_brand_name(brand) == brand


def test_a_brand_that_only_needs_a_suffix_stripped_keeps_its_own_name():
    # Not in the table, but "Bikes" is still a suffix — and stripping it would
    # be a guess, so the raw name stands.
    assert canonical_brand_name("Blitzen Bikes") == "Blitzen Bikes"


# --- recovering a brand that is really a shop or a distributor ---------------

@pytest.mark.parametrize(
    "brand, model_name, vendor_name, expected",
    [
        # Distributors fronting for real marques.
        ("Advance Traders", "Merida eBIG NINE 600 - SILK BLUE/BLACK", "Bicycle Centre Belmont", "Merida"),
        ("Advance Traders", "2023 Norco Runner", "The Mountain Biker", "Norco"),
        ("Monza Imports", 'Mongoose Switchback 20"', "Bicycle Centre Belmont", "Mongoose"),
        ("Sheppard Cycles", "2026 Scott Voltage", "The Mountain Biker", "Scott"),
        ("Pon Performance", "2025 Santa Cruz Nomad", "Wheelhaus", "Santa Cruz"),
        # Placeholders.
        ("Not specified", "JAMIS Durango A2 19 Midnight blue", "Fitzroy Cycles", "Jamis"),
        ("My Store", "2018 Canyon Strive CF 9.0", "West Coast Cycles", "Canyon"),
        ("global", "Icon EB One", "Bicycle Centre Belmont", "Icon"),
        # A shop using its own name as the brand — caught by comparing to the
        # vendor, with no list of shop names to maintain.
        ("Bicycle Workshop", "Giant TCR Advanced Disc 1 Pro", "Bicycle Workshop", "Giant"),
        ("Bicycle Workshop", "Liv Embolden 2 2023", "Bicycle Workshop", "Liv"),
        ("The Mountain Biker", "2026 Yeti MTe", "The Mountain Biker", "Yeti"),
        ("Happy Wheels", "Cervelo R5 Force AXS (2023) 58cm", "Happy Wheels", "Cervélo"),
        ("Off Course", "Salsa Stormchaser Singlespeed 2024", "Off Course", "Salsa"),
        ("Live Life Cycling", "Pinarello Dogma F Luxter Venice 56", "Live Life Cycling", "Pinarello"),
        ("Mackay Cycles", "Cervelo 56cm - Ex Demo", "Mackay Cycles", "Cervélo"),
    ],
)
def test_brand_is_recovered_from_the_model_name(brand, model_name, vendor_name, expected):
    assert canonical_brand_name(brand, model_name, vendor_name) == expected


def test_recovery_skips_a_leading_model_year():
    assert brand_from_model_name("2025 Santa Cruz Nomad") == "Santa Cruz"
    assert brand_from_model_name("Santa Cruz Nomad") == "Santa Cruz"


def test_recovery_prefers_the_longest_brand_match():
    """"Santa Cruz Nomad" is a Santa Cruz, and there is no brand called Santa —
    but if one is ever added, the two-word match must still win."""
    assert brand_from_model_name("Santa Cruz Hightower") == "Santa Cruz"


def test_recovery_that_finds_nothing_leaves_the_brand_alone():
    """The guard that keeps a shop's own-brand bikes labelled.

    Progear Bikes is both a vendor and a real brand. Its house-brand products
    do not name a manufacturer in the title, so recovery finds nothing and the
    brand survives — only stripped of its corporate suffix.
    """
    assert canonical_brand_name(
        "Progear Bikes", 'DuraLite Kids Balance Bike 12" - Pearl White', "Progear Bikes"
    ) == "Progear"
    assert canonical_brand_name("Bikecorp", "BC Shadow Gravel", "Bike Force Joondalup") == "Bikecorp"


def test_recovery_never_invents_a_brand():
    """It can only return a name already in the canonical vocabulary."""
    assert brand_from_model_name("Whizzbang Turbo Deluxe 9000") is None


# --- the Giant franchise ------------------------------------------------------

@pytest.mark.parametrize(
    "brand",
    ["Giant Brisbane", "Giant Lygon St", "Giant South Yarra", "GIANT", "Giant Bicycles",
     "Giant Bikes Wollongong", "Giant Sunshine Coast", "Giant Australia"],
)
def test_every_giant_storefront_is_giant(brand):
    assert canonical_brand_name(brand) == "Giant"


def test_the_giant_rule_does_not_swallow_other_brands():
    # A prefix rule is used only for Giant; scrapers/models.py documents why
    # "Liv" must never prefix-match "Live Life Cycling".
    assert canonical_brand_name("Liv") == "Liv"
    assert canonical_brand_name("Live Life Cycling", "Some Bike", "Somewhere Else") == "Live Life Cycling"


# --- the reason this matters beyond the dropdown ------------------------------

def test_normalising_the_brand_repairs_cross_shop_matching():
    """product_key is <canonical brand>:<sku>, so two shops spelling a brand
    differently were never compared. Accents are the case that got through the
    suffix stripping in make_product_key."""
    a = _record(brand="Cervelo", sku="R5-58")
    b = _record(brand="Cervélo", sku="R5-58", id="b")
    c = _record(brand="CERVELO", sku="R5-58", id="c")
    assert a.brand == b.brand == c.brand == "Cervélo"
    assert a.product_key == b.product_key == c.product_key

    # And the same two, unnormalised, are what the split looked like.
    assert make_product_key("Cervelo", "R5-58") != make_product_key("Cervélo", "R5-58")


def test_recovered_brand_feeds_the_product_key():
    record = _record(
        brand="Advance Traders", model_name="Merida eBIG NINE 600", sku="ME600",
        vendor_name="Bicycle Centre Belmont",
    )
    assert record.brand == "Merida"
    assert record.product_key == make_product_key("Merida", "ME600")


def test_brand_is_normalised_before_the_product_key_is_derived():
    """Validator order is declaration order. If it flipped, product_key would be
    built from the raw brand and this whole change would be cosmetic."""
    record = _record(brand="NORCO", sku="S1")
    assert record.brand == "Norco"
    assert record.product_key.startswith("norco:")


def test_fold_ignores_case_accents_punctuation_and_suffixes():
    assert fold_brand("Norco Bicycles") == fold_brand("NORCO") == "norco"
    assert fold_brand("Cervélo") == fold_brand("CERVELO") == "cervelo"
    assert fold_brand("X-LAB") == fold_brand("X-lab") == "xlab"
    # Never strip to a stub.
    assert fold_brand("ET Cycle") == "etcycle"


def _record(**overrides):
    now = datetime.now(timezone.utc)
    data = dict(
        id="a", vendor_name="Shop", city="Sydney", brand="Trek",
        model_name="Domane SL5", category="Road", frame_size="M",
        price_original=None, price_sale=1000.0, discount_percentage=0,
        in_stock=True, product_url="https://x/p", image_url=None,
        scraped_at=now, last_seen_at=now,
    )
    data.update(overrides)
    return BikeRecord(**data)
