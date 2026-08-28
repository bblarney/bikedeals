"""Caption rules for the daily Instagram post."""
from datetime import date

from social.caption import build_caption, format_price
from tests.test_social_select import make_deal


def test_ad_disclosure_is_the_first_line():
    """Instagram folds the caption after ~2 lines, and the ACCC expects the
    disclosure to be prominent. Anywhere but the top and it can be hidden
    behind "... more"."""
    caption = build_caption(make_deal(), deal_count=12)
    assert caption.splitlines()[0] == "#ad"


def test_carries_both_prices_and_the_discount():
    caption = build_caption(make_deal(price_original=3000.0, price_sale=2100.0), deal_count=12)
    assert "Was $3,000" in caption
    assert "Now $2,100" in caption
    assert "(30% off)" in caption


def test_credits_the_shop_and_city():
    caption = build_caption(make_deal(), deal_count=12)
    assert "at Test Cycles, Sydney" in caption


def test_omits_the_city_when_the_shop_has_none():
    caption = build_caption(make_deal(city=None), deal_count=12)
    assert "at Test Cycles" in caption
    assert "Test Cycles," not in caption


def test_openers_rotate_across_days():
    bike = make_deal()
    captions = {
        build_caption(bike, deal_count=12, on=date(2026, 1, day)).splitlines()[1]
        for day in range(1, 8)
    }
    assert len(captions) > 1


def test_a_single_deal_day_does_not_say_zero_others():
    caption = build_caption(make_deal(), deal_count=1)
    assert "0 other deals" not in caption
    assert "bikegrid.com.au" in caption


def test_category_hashtags_follow_the_bike():
    assert "#mtb" in build_caption(make_deal(category="Mountain"), deal_count=5)
    assert "#roadbike" in build_caption(make_deal(category="Road"), deal_count=5)


def test_price_formatting_drops_meaningless_cents():
    assert format_price(2100.0) == "$2,100"
    assert format_price(2100.5) == "$2,100.50"
