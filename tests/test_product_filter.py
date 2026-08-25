"""The not-a-bike gate.

Every case here is a real listing from the live feed. The false-positive tests
matter more than the true-positive ones: missing an accessory leaves one junk
row, but a rule that eats a real bike deletes inventory silently and nobody
finds out from the outside.
"""
import pytest

from scrapers.product_filter import drop_non_bikes, non_bike_reason
from tests.conftest import make_bike


def reason(model_name, frame_size="M", price_sale=1500.0, brand="Trek"):
    return non_bike_reason(model_name, frame_size, price_sale, brand)


# --- things that are not bikes ---------------------------------------------

@pytest.mark.parametrize(
    "model_name, expected",
    [
        ("Rascal Kids Purple Streamer", "accessory:streamer"),
        ("Rascal Kids Spoke Beads Mixed Colors Spokey Dokes", "accessory:spoke"),
        ("Arisun 20x1.50/2.2 Schrader Valve (Online Price Only)", "accessory:valve"),
        ("Front Basket Black - E-Cargo Bike", "accessory:basket"),
        ("Footboards Black - E-Cargo Bike", "accessory:footboards"),
        ("Tribe Seat Pad", "accessory:seat pad"),
        ("Still Good: SRAM RED CHAINRING DM X-SYNC BLACK/SILVER - 42T", "accessory:chainring"),
        ("OAKLEY RADAR EV PATH MATTE BLACK W/ PRIZM ROAD", "accessory:oakley"),
        ("Yakima HighRoad Roof Mount Bike Carrier", "accessory:yakima"),
    ],
)
def test_accessory_names_are_rejected(model_name, expected):
    assert reason(model_name) == expected


def test_tyre_named_without_the_word_tyre_is_rejected():
    # "Vittoria Terreno Dry 700x38 TNT Gravel G2" contains no accessory noun,
    # and resolve_category happily filed it under Gravel.
    assert reason("Vittoria Terreno Dry 700x38 TNT Gravel G2 - Anth Black") == "tyre-dimensions"


def test_tyre_width_as_a_frame_size_is_rejected():
    # Live: "CADEX RACE GC" listed at frame_size 28mm and 30mm for $119.95.
    assert reason("CADEX RACE GC", frame_size="28mm", price_sale=119.95) == "tyre-width-size"


def test_component_brand_is_rejected():
    assert reason("Terreno Dry", brand="Vittoria") == "component-brand"
    assert reason("RED AXS", brand="SRAM") == "component-brand"


def test_price_floor_catches_junk_with_no_giveaway_word():
    assert reason("Rascal Windmill Pink 360 Rotation Toy", price_sale=6.99) == "below-price-floor"


# --- things that ARE bikes and must survive ---------------------------------
#
# Each of these was deleted by an earlier draft of the rules, which is why the
# rule that deleted it is named in the comment.

def test_ebike_advertising_its_battery_survives():
    # `battery` as a term removed 84 real e-bikes from a 5,478-row sample.
    assert reason("Merida eOne-Sixty 6000 Electric Enduro Bike 600Wh Battery", price_sale=5999.0) is None
    assert reason("Specialized 2026 S-works Turbo Levo R 111NM Torque 850W Power", price_sale=20900.0) is None


def test_bike_named_charger_survives():
    # Norco ships a mountain bike called the Charger.
    assert reason("Norco Charger 3", price_sale=1099.0, brand="Norco") is None


def test_three_wheel_trike_survives():
    # `wheel` took "Papa Grande Pro - 3 Wheel E-Trike by Vamos", $6,395.
    assert reason("Papa Grande Pro - 3 Wheel E-Trike by Vamos", price_sale=6395.0, brand="Vamos") is None


def test_bike_whose_name_mentions_its_wheelset_survives():
    assert reason("Specialized Tero X 4.0 (29/27.5 Wheelset LARGE XL AVAILABLE)", price_sale=4000.0) is None


def test_rim_brake_road_bike_survives():
    # `rim` took "2026 Merida Scultura Rim 100", a $999 road bike.
    assert reason("2026 Merida Scultura Rim 100", price_sale=999.0, brand="Merida") is None


def test_byk_kids_bikes_survive_the_tyre_dimension_rule():
    # ByK model names *are* "E-450x8" / "E-620x7"; a loose \d{2,3}x\d matched
    # them and deleted four real kids' bikes.
    for name in ("E-450x8  Kids Hybrid Bike White/Dusty Green",
                 "ByK E-620x7 Kids Mountain Road Bike MTR Titanium & Dark Blue",
                 "ByK E-620x9 MTB Kids Mountain Bike",
                 "ByK E-450x1  MTBG Kids Mountain Bike Dusty Sage Green"):
        assert reason(name, price_sale=499.0, brand="ByK") is None, name


def test_component_brands_that_also_build_bikes_survive():
    # ENVE sells complete builds; Hornit makes bells *and* the AIRO balance bike.
    assert reason("ENVE Melee - Wheelhaus Demo Build", price_sale=13500.0, brand="ENVE") is None
    assert reason("Hornit AIRO 12 inch Balance Bike - Green", price_sale=399.0, brand="Hornit") is None


def test_cheap_kids_bikes_survive_the_price_floor():
    # The $150-700 band is almost entirely real kids' and balance bikes, so the
    # floor sits below the cheapest genuine one ($89 Holstar Blaster 12").
    assert reason("Holstar Blaster 12\" Kids Bike - Orange/Grey (Boxed)", price_sale=89.0) is None
    assert reason("Cruzee UltraLite 12'' Balance Bike Red", price_sale=198.0) is None
    assert reason("Classic Vintage 12\" Balance Bike Lavender", frame_size="12 inch", price_sale=99.99) is None


def test_bikes_with_component_words_in_spec_text_survive():
    assert reason("Trek Domane SL5 Shimano 105 Di2", price_sale=4299.0) is None
    assert reason("Giant Trance X Advanced Pro 29 1", price_sale=7999.0) is None
    assert reason("Merida Big Nine 400 Mountain Bike", price_sale=1299.0) is None


# --- the split, and what it must not disturb --------------------------------

def test_drop_non_bikes_splits_and_counts_by_reason():
    kept, rejected = drop_non_bikes([
        make_bike(id="b1", model_name="Domane SL5"),
        make_bike(id="b2", model_name="Rascal Kids Purple Streamer"),
        make_bike(id="b3", model_name="Front Basket Black"),
        make_bike(id="b4", model_name="Rear Basket Black"),
    ])
    assert [b.id for b in kept] == ["b1"]
    assert rejected == {"accessory:streamer": 1, "accessory:basket": 2}


def test_drop_non_bikes_on_an_all_bikes_batch_changes_nothing():
    batch = [make_bike(id=f"b{i}", model_name="Domane SL5") for i in range(5)]
    kept, rejected = drop_non_bikes(batch)
    assert len(kept) == 5
    assert rejected == {}


def test_titles_the_old_shopify_word_set_deleted_are_kept():
    """Real bikes recovered by moving title screening off _ACCESSORY_WORDS.

    All observed live at one vendor, in two pages of one collection.
    """
    for name, price in (
        ("BYK E-540x9 9 Speed Disc Brake Kids Gravel Bike Slate Grey/Gold", 798.0),
        ("FirstBIKE Cross Balance Bike with Brake", 260.0),
        ("Kids Ride Shotgun Dirt Hero Balance Bike 12\" with Magura Brakes", 836.0),
        ("Early Rider Charger 12\" Kids Bike", 437.0),
        ("Shogun eMetro Electric Urban Bike Light Grey", 1791.0),
    ):
        assert reason(name, price_sale=price) is None, name


def test_titles_the_shopify_word_set_caught_are_still_caught():
    """Behaviour the move must not lose: framesets and scooters stay out."""
    assert reason("Safi Works Form R32.1 Road Frameset") == "accessory:frameset"
    assert reason("Micro Sprite Scooter", price_sale=199.0) == "accessory:scooter"
    assert reason("Whiskey Thumb Throttle", price_sale=70.0) == "accessory:throttle"
