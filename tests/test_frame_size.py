"""Canonical frame sizes.

Every raw value here is one the live size facet actually served. The facet had
536 distinct entries for roughly fifty real sizes.
"""
import importlib.util
import pathlib

import pytest

from scrapers.models import BikeRecord, make_bike_id
from scrapers.utils import canonical_frame_size


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Thirty spellings of Large, all live values.
        ("L", "L"), ("Lg", "L"), ("LG", "L"), ("LGE", "L"), ("LRG", "L"),
        ("Large", "L"), ("LARGE", "L"), ("LARGE - 56", "L"), ("Large 29\"", "L"),
        ("Large 29\" Wheels", "L"), ("L (Large 170cm - 185cm)", "L"),
        ("L (29\" wheel)", "L"), ("L - 57.5", "L"), ("19\" (LRG)", "L"),
        ("56 (L)", "L"), ("L (EX-DEMO)", "L"), ("L56", "L"),
        # Small and medium, including the abbreviations that sit beside LG/MD.
        ("S", "S"), ("SM", "S"), ("Sm", "S"), ("SML", "S"), ("Small", "S"),
        ("16\" Small", "S"), ("51cm - Small", "S"), ("S (Second-Hand)", "S"),
        ("M", "M"), ("MD", "M"), ("MED", "M"), ("Medium", "M"), ("MEDIUM - 54", "M"),
        ("54 (M)", "M"), ("29 Medium", "M"), ("M - 54.5", "M"), ("M54", "M"),
        # The extremes, where "large" must not win over "xx-large".
        ("XL", "XL"), ("X-Large", "XL"), ("Extra Large", "XL"), ("46\" XLarge", "XL"),
        ("X-Large - 58", "XL"), ("21 (XL)", "XL"),
        ("XXL", "XXL"), ("2XL", "XXL"), ("2X-LARGE", "XXL"), ("XX-Large 61cm", "XXL"),
        ("2X-Large - 61", "XXL"), ("XXL61", "XXL"),
        ("XS", "XS"), ("X-Small", "XS"), ("Extra-small", "XS"), ("XS-46", "XS"),
        ("XXS", "XXS"), ("2XS", "XXS"), ("XX-Small 47cm", "XXS"),
        ("3XS", "XXXS"), ("4XS", "XXXS"),
        # Specialized S-Sizing, ~5% of the catalogue.
        ("S1", "XS"), ("S2", "S"), ("S3", "M"), ("S4", "L"), ("S5", "XL"), ("S6", "XXL"),
        # Intermediates.
        ("ML", "M/L"), ("M\\L", "M/L"), ("Medium-Large", "M/L"),
        ("S\\M", "S/M"), ("50cm (S/M)", "S/M"),
        # Road centimetres, however they are punctuated.
        ("54", "54cm"), ("54cm", "54cm"), ("54 CM", "54cm"), ("54CM", "54cm"),
        ("54cm 700c", "54cm"), ("51cm | Reach 40cm", "51cm"),
        ("54 (Integrated Barstem 400MM / 110MM)", "54cm"),
        ("48.5CM", "48.5cm"), ("47cm | Grey-Curry (arr Jun)", "47cm"),
        ("560", "56cm"),   # millimetres
        ("40.5", "40.5cm"),  # the small end of the cm range, not a stray number
        # Kids' wheels and inch-numbered frames.
        ("12", '12"'), ("12 INCH", '12"'), ("12in", '12"'), ("12inch", '12"'),
        ("16\"", '16"'), ("20 Inch", '20"'), ("24inch - G", '24"'),
    ],
)
def test_canonicalises_live_values(raw, expected):
    assert canonical_frame_size(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        # Unknown, not a size.
        "N/A", "One Size", "", None,
        # Colours, which leaked in through extract_frame_size's fallback.
        "Chrome Blue", "Light Blue", "Brushed Alloy Silver", "Chrome Line Green",
        # Not a frame size at all.
        "Frameset only", "Complete bike", "Kids", "28mm",
        # Wheel diameters. "29" is not a size you can pick between.
        "26\"", "27.5", "29", "26 Inches", "23 INCH",
        # Top-tube lengths, which one shop publishes instead of a size. These
        # are the dangerous ones: the digits look like sizes, and an earlier
        # draft turned "18.50 TT" through "21.50 TT" into 50cm frames and
        # "20.65 TT" into a 65cm frame.
        "20.50 TT", "20.50 TT RSD", "18.50 TT", "21.00 TT RHD", "20.65 TT",
        # Bare numbers below the smallest real frame size.
        "1", "2", "3",
    ],
)
def test_non_sizes_canonicalise_to_none(raw):
    assert canonical_frame_size(raw) is None


def test_sm_is_small_not_small_medium():
    """Bare SM sits next to MD and LG in the data, 197 times in 5,478 rows.

    It is the Small in Small/Medium/Large. A genuine intermediate writes the
    separator, and only then is it read as one.
    """
    assert canonical_frame_size("SM") == "S"
    assert canonical_frame_size("S\\M") == "S/M"
    assert canonical_frame_size("Small/Medium") == "S/M"


# --- the constraint that makes this safe to ship ------------------------------

def test_canonicalising_does_not_change_a_bike_id():
    """ids hash the raw size, so normalising cannot break a detail URL.

    bikes.id is in every detail URL, every shared link, the sitemap, and the
    bike_id that price_events joins on. If canonicalisation fed the hash, this
    change would silently orphan every price history on the site.
    """
    before = make_bike_id("Shop", "https://x/p", "LARGE - 56", "Sydney")
    record = _record(frame_size="LARGE - 56")
    assert record.frame_size_canonical == "L"
    assert record.frame_size == "LARGE - 56", "the raw value must survive"
    assert make_bike_id("Shop", "https://x/p", record.frame_size, "Sydney") == before


def test_record_derives_canonical_and_ignores_a_hand_set_one():
    assert _record(frame_size="MEDIUM").frame_size_canonical == "M"
    forged = _record(frame_size="MEDIUM", frame_size_canonical="XXL")
    assert forged.frame_size_canonical == "M"


def test_unknown_size_records_none_rather_than_a_guess():
    assert _record(frame_size="N/A").frame_size_canonical is None
    assert _record(frame_size="Chrome Blue").frame_size_canonical is None


def _record(**overrides):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    data = dict(
        id="x", vendor_name="Shop", city="Sydney", brand="Trek",
        model_name="Domane", category="Road", frame_size="M",
        price_original=None, price_sale=1000.0, discount_percentage=0,
        in_stock=True, product_url="https://x/p", image_url=None,
        scraped_at=now, last_seen_at=now,
    )
    data.update(overrides)
    return BikeRecord(**data)


# --- the migration's frozen copy must not drift -------------------------------

def _load_migration():
    path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "migrations" / "versions" / "a7d3e91c5f28_add_frame_size_canonical.py"
    )
    spec = importlib.util.spec_from_file_location("_frame_size_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_backfill_agrees_with_the_scraper():
    """The backfill carries a frozen copy of canonical_frame_size, per the
    precedent in f6a3c81b4d92. If the two disagree, rows written by the
    migration and rows written by tonight's run land under different sizes."""
    frozen = _load_migration().canonical_frame_size
    corpus = [
        "L", "Lg", "LARGE - 56", "Large 29\"", "SM", "MD", "S3", "M54",
        "54", "54cm", "560", "48.5CM", "12inch", "24\"", "ML", "S\\M",
        "N/A", "One Size", "Chrome Blue", "Frameset only", "20.50 TT",
        "29", "27.5", "2X-Large - 61", "X-Small 48cm", "XXS (26\")",
    ]
    for raw in corpus:
        assert frozen(raw) == canonical_frame_size(raw), raw
