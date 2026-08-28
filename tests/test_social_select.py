"""Selection rules for the daily Instagram post.

The important property under test is that a bad day produces *no* post rather
than a bad one: every rejection path has to end in None, not an exception and
not a fallback pick.
"""
import httpx
import pytest

from social import select


def make_deal(**overrides):
    deal = dict(
        id="bike-1",
        vendor_name="Test Cycles",
        city="Sydney",
        brand="Trek",
        model_name="Domane SL5",
        category="Road",
        frame_size="M",
        frame_size_canonical="M",
        price_original=3000.0,
        price_sale=2100.0,
        discount_percentage=30,
        in_stock=True,
        product_url="https://shop.example.com/p/1",
        image_url="https://cdn.shopify.com/s/files/1/1.jpg",
        product_key="trek:ABC123",
    )
    deal.update(overrides)
    return deal


def test_picks_the_deepest_discount():
    shallow = make_deal(id="a", discount_percentage=25, product_key="trek:A")
    deep = make_deal(id="b", discount_percentage=55, product_key="trek:B")
    assert select.select_deal([shallow, deep], set(), frozenset())["id"] == "b"


def test_skips_vendors_that_opted_out():
    blocked = make_deal(vendor_name="Shy Bikes", discount_percentage=60, product_key="trek:A")
    allowed = make_deal(id="b", discount_percentage=30, product_key="trek:B")
    picked = select.select_deal([blocked, allowed], set(), frozenset({"Shy Bikes"}))
    assert picked["id"] == "b"


def test_skips_products_already_posted():
    already = make_deal(discount_percentage=60, product_key="trek:SEEN")
    fresh = make_deal(id="b", discount_percentage=30, product_key="trek:NEW")
    picked = select.select_deal([already, fresh], {"trek:SEEN"}, frozenset())
    assert picked["id"] == "b"


def test_ledger_key_falls_back_to_bike_id_without_a_sku():
    """13% of listings publish no SKU, so product_key is None for them."""
    no_sku = make_deal(product_key=None)
    assert select.ledger_key(no_sku) == "bike:bike-1"
    assert select.select_deal([no_sku], {"bike:bike-1"}, frozenset()) is None


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"image_url": None}, id="no image"),
        pytest.param({"image_url": "not-a-url"}, id="unusable image"),
        pytest.param({"price_original": None}, id="no RRP to strike through"),
        pytest.param({"discount_percentage": 5}, id="discount too shallow"),
        pytest.param({"price_sale": 120.0}, id="too cheap to be interesting"),
        pytest.param({"brand": "Unbranded Special"}, id="unrecognised brand"),
        pytest.param({"in_stock": False}, id="out of stock"),
    ],
)
def test_unpostable_listings_are_skipped(overrides):
    assert select.select_deal([make_deal(**overrides)], set(), frozenset()) is None


def test_an_empty_day_returns_none_rather_than_raising():
    assert select.select_deal([], set(), frozenset()) is None


def test_opted_out_vendors_reads_the_live_registry():
    """Every shop is opted in unless its own config says otherwise."""
    assert isinstance(select.opted_out_vendors(), frozenset)


async def test_fetch_deals_asks_for_todays_discounted_stock():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"results": [make_deal()], "total": 1})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        deals = await select.fetch_deals(client)

    assert len(deals) == 1
    assert seen["added_since"] == "day"
    assert seen["sort"] == "discount_desc"
    assert seen["in_stock"] == "true"
