"""RRPs a shop's own data contradicts.

The case that motivated this is real: Saint Cloud publishes six variants of the
Giant Propel Advanced Pro 0-Di2, five with compare_at_price 8499.00 and the XL
with 84990.00. At 91% off it was the first row of the default sort, which is
the first thing every visitor to the site saw.
"""
from datetime import datetime, timezone

from scrapers.models import BikeRecord
from scrapers.price_sanity import MAX_PLAUSIBLE_DISCOUNT, drop_implausible_rrp


def test_the_variant_with_the_stray_zero_loses_its_rrp():
    variants = [
        _record(id=f"v{i}", frame_size=size, price_sale=7799.0, price_original=8499.0)
        for i, size in enumerate(["XS", "S", "M", "ML", "L"])
    ]
    odd = _record(id="xl", frame_size="XL", price_sale=7799.0, price_original=84990.0)

    kept, reasons = drop_implausible_rrp(variants + [odd])

    assert reasons == {"rrp-disagrees-with-siblings": 1}
    assert odd.price_original is None
    assert odd.discount_percentage == 0
    # The bike itself stays in the catalogue, at the price it really sells for.
    assert odd in kept
    assert odd.price_sale == 7799.0
    # And its siblings keep their genuine 8%.
    assert all(v.price_original == 8499.0 and v.discount_percentage == 8 for v in variants)


def test_a_real_clearance_across_every_size_is_untouched():
    """The 69% Cannondale SuperSix EVO Neo in the live feed is a real run-out.

    A discount cap tight enough to catch 91% would have to delete this.
    """
    variants = [
        _record(id=f"v{i}", frame_size=s, price_sale=2459.0, price_original=7999.0)
        for i, s in enumerate(["S", "M", "L", "XL"])
    ]
    kept, reasons = drop_implausible_rrp(variants)
    assert reasons == {}
    assert all(v.price_original == 7999.0 for v in kept)


def test_a_spread_of_real_prices_within_one_group_is_not_a_typo():
    # Sizes of one model priced slightly differently is normal; 3x is not.
    variants = [
        _record(id="a", price_original=4000.0, price_sale=3000.0),
        _record(id="b", price_original=4200.0, price_sale=3100.0),
        _record(id="c", price_original=4500.0, price_sale=3300.0),
    ]
    _, reasons = drop_implausible_rrp(variants)
    assert reasons == {}


def test_grouping_survives_an_affiliate_rewritten_url():
    """Grouping on product_url put 538 unrelated products in one group.

    Affiliate vendors rewrite every product onto a single tracking link, so the
    URL is not the identity of a product. Two different bikes sharing a URL must
    not be treated as sizes of each other.
    """
    cheap = [
        _record(id=f"c{i}", model_name="Reid Ladies Classic", price_original=429.99,
                price_sale=299.99, product_url="https://aff.example/c/1")
        for i in range(5)
    ]
    pricey = [
        _record(id=f"p{i}", model_name="Polygon Helios A8", price_original=6699.99,
                price_sale=4499.99, product_url="https://aff.example/c/1")
        for i in range(3)
    ]
    _, reasons = drop_implausible_rrp(cheap + pricey)
    assert reasons == {}, "an expensive bike is not a typo for a cheap one"
    assert all(b.price_original == 6699.99 for b in pricey)


def test_two_siblings_are_not_enough_to_convict():
    """With two priced variants there is no majority — either could be the typo,
    so the sibling rule stays out of it."""
    a = _record(id="a", price_original=1000.0, price_sale=900.0)
    b = _record(id="b", price_original=90000.0, price_sale=900.0)
    _, reasons = drop_implausible_rrp([a, b])
    assert "rrp-disagrees-with-siblings" not in reasons


def test_lone_product_falls_back_to_the_plausibility_cap():
    lone = _record(id="lone", price_sale=500.0, price_original=50000.0)
    assert lone.discount_percentage >= MAX_PLAUSIBLE_DISCOUNT
    _, reasons = drop_implausible_rrp([lone])
    assert reasons == {"discount-beyond-plausible": 1}
    assert lone.price_original is None


def test_the_cap_sits_above_every_genuine_discount_seen():
    """Largest real discount in the live catalogue is 69%. The cap must not be
    anywhere near it, because it cannot tell a clearance from a typo."""
    assert MAX_PLAUSIBLE_DISCOUNT > 69
    lone = _record(id="lone", price_sale=2459.0, price_original=7999.0)  # 69%
    _, reasons = drop_implausible_rrp([lone])
    assert reasons == {}
    assert lone.price_original == 7999.0


def test_listings_without_an_rrp_are_ignored():
    rows = [_record(id=f"n{i}", price_original=None, price_sale=1000.0) for i in range(4)]
    kept, reasons = drop_implausible_rrp(rows)
    assert reasons == {}
    assert len(kept) == 4


def _record(**overrides):
    now = datetime.now(timezone.utc)
    data = dict(
        id="a", vendor_name="Saint Cloud", city="Melbourne", brand="Giant",
        model_name="Giant Propel Advanced Pro 0-Di2 2027", category="Road",
        frame_size="M", price_original=None, price_sale=1000.0,
        discount_percentage=0, in_stock=True,
        product_url="https://saintcloud.com.au/products/propel", image_url=None,
        scraped_at=now, last_seen_at=now,
    )
    data.update(overrides)
    record = BikeRecord(**data)
    # compute_discount is applied by the pipelines, not the model, so mirror it
    # here rather than hand-setting a percentage that could disagree.
    if record.price_original and record.price_original > record.price_sale:
        record.discount_percentage = round((1 - record.price_sale / record.price_original) * 100)
    return record
