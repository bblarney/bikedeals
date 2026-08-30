"""Tests for the Lightspeed eCom pipeline.

The three behaviours worth pinning down are the ones that fail silently against
a live shop: pagination by path segment (a query parameter returns HTTP 200 and
re-serves page one), recursion into subcategory grids, and reading the frame
size off the size axis rather than the colour axis.
"""
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
import pytest

from scrapers.models import VendorConfig
from scrapers.pipelines import lightspeed as ls
from scrapers.pipelines.lightspeed import (
    _build_record,
    _category_candidates,
    _frame_size,
    _is_electric,
    _price_pair,
    scrape_lightspeed,
)

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_delay(monkeypatch):
    monkeypatch.setattr(ls, "SCRAPER_DELAY_RANGE", (0.0, 0.0))


def make_config(**overrides) -> VendorConfig:
    base = dict(
        vendor_name="Test Cycles",
        city="Perth",
        base_url="https://shop.example",
        pipeline="lightspeed",
        collections=["bikes"],
        category_map={
            "electric-bikes": "E-Bike",
            "mountain-bikes": "Mountain",
            "gravel": "Gravel",
            "road": "Road",
            "kids": "Commuter",
        },
    )
    base.update(overrides)
    return VendorConfig(**base)


def make_product(pid=1, vid=10, **overrides) -> dict:
    base = {
        "id": pid,
        "vid": vid,
        "image": 555,
        "sku": "SKU-1",
        "title": "Cannondale SuperSix EVO 4",
        "url": "cannondale-supersix-evo-4.html",
        "brand": {"title": "Cannondale"},
        "price": {"price_incl": 2999, "price_old_incl": 4499},
        "available": True,
        "variant": '"Size: 56","Colour: Jet Black"',
    }
    base.update(overrides)
    return base


def listing(products, count=None, pages=1) -> dict:
    return {
        "shop": {"id": 663013},
        "collection": {
            "count": count if count is not None else len(products),
            "pages": pages,
            "limit": 100,
            "products": {str(p["id"]): p for p in products},
        },
    }


def tree(*child_paths, types=None) -> dict:
    types = types or {}
    return {
        "shop": {"id": 663013},
        "catalog": {
            "categories": {
                str(i): {"url": path, "title": path, "type": types.get(path, "category")}
                for i, path in enumerate(child_paths)
            }
        },
    }


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- pure helpers -------------------------------------------------------------

@pytest.mark.parametrize("segment,expected", [
    ("e-bikes", True), ("ebikes", True), ("electric-bikes", True),
    ("e-bike-off-road", True), ("mountain-e-bikes", True),
    ("road", False), ("mountain-bikes", False), ("gravel", False),
])
def test_is_electric(segment, expected):
    assert _is_electric(segment) is expected


def test_category_candidates_are_deepest_segment_first():
    assert _category_candidates("bikes/mountain-bikes/enduro", "Some Bike") == [
        "enduro", "mountain-bikes", "bikes", "some bike",
    ]


def test_category_candidates_put_electric_segments_first():
    """A shop nesting /e-bikes/mountain/ must not file its e-MTBs as Mountain."""
    candidates = _category_candidates("e-bikes/mountain", "Levo Comp")
    assert candidates[0] == "e-bikes"


def test_frame_size_reads_the_size_axis_not_the_colour():
    assert _frame_size('"Size: 56","Colour: Jet Black"') == "56"
    assert _frame_size('"Colour: Forge Grey","Size: Medium"') == "Medium"


def test_frame_size_is_na_when_there_is_no_size_axis():
    assert _frame_size('"Colour: Forge Grey"') == "N/A"
    assert _frame_size(None) == "N/A"


def test_price_pair_treats_zero_old_price_as_no_discount():
    assert _price_pair({"price_incl": 2999, "price_old_incl": 0}) == (2999.0, None)


def test_price_pair_ignores_an_old_price_that_is_not_higher():
    assert _price_pair({"price_incl": 2999, "price_old_incl": 2999}) == (2999.0, None)


def test_price_pair_rejects_a_missing_price():
    assert _price_pair({"price_incl": 0, "price_old_incl": 4499}) == (None, None)


# --- record building ----------------------------------------------------------

def test_build_record_maps_every_field():
    record = _build_record(make_config(), make_product(), "bikes/road", 663013, NOW)

    assert record.brand == "Cannondale"
    assert record.category == "Road"
    assert record.frame_size == "56"
    assert record.price_sale == 2999
    assert record.price_original == 4499
    assert record.discount_percentage == 33
    assert record.in_stock is True
    assert record.sku == "SKU-1"
    assert record.product_url == "https://shop.example/cannondale-supersix-evo-4.html"
    assert record.image_url == (
        "https://cdn.shoplightspeed.com/shops/663013/files/555/500x500x2/image.jpg"
    )


def test_a_missing_brand_is_recovered_from_the_model_name():
    """No brand field means the vendor name, which brands.py then recovers from."""
    record = _build_record(
        make_config(), make_product(brand={}), "bikes/road", 663013, NOW
    )
    assert record.brand == "Cannondale"


def test_a_missing_brand_falls_back_to_the_vendor_name_when_unrecoverable():
    record = _build_record(
        make_config(),
        make_product(brand={}, title="Weekender Step-Through"),
        "bikes/road", 663013, NOW,
    )
    assert record.brand == "Test Cycles"


def test_brand_map_overrides_the_shops_brand_field():
    config = make_config(brand_map={"Cannondale Australia": "Cannondale"})
    record = _build_record(
        config,
        make_product(brand={"title": "Cannondale Australia"}),
        "bikes/road", 663013, NOW,
    )
    assert record.brand == "Cannondale"


def test_build_record_omits_the_image_when_the_product_has_none():
    record = _build_record(
        make_config(), make_product(image=0), "bikes/road", 663013, NOW
    )
    assert record.image_url is None


def test_build_record_returns_none_when_no_category_matches():
    record = _build_record(
        make_config(), make_product(), "bikes/unicycles", 663013, NOW
    )
    assert record is None


def test_collection_category_map_overrides_the_path_segments():
    config = make_config(collection_category_map={"bikes/road": "Gravel"})
    record = _build_record(config, make_product(), "bikes/road", 663013, NOW)
    assert record.category == "Gravel"


# --- walking and pagination ---------------------------------------------------

async def test_pagination_uses_the_path_segment_not_a_query_parameter():
    """`&page=2` silently re-serves page one, so it must never be used."""
    page1 = [make_product(pid=i, vid=i * 10) for i in range(1, 101)]
    page2 = [make_product(pid=i, vid=i * 10) for i in range(101, 151)]
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = urlparse(str(request.url)).path
        requests.append(path)
        if path == "/bikes/page2.html":
            return httpx.Response(200, json=listing(page2, count=150, pages=2))
        return httpx.Response(200, json=listing(page1, count=150, pages=2))

    bikes, invalid = await scrape_lightspeed(
        make_config(collections=["bikes"], category_map={"bikes": "Road"}),
        make_client(handler),
    )

    assert invalid == 0
    assert len(bikes) == 150
    assert "/bikes/page2.html" in requests
    assert not any("page=" in urlparse(r).query for r in requests)


async def test_walk_recurses_into_subcategory_grids():
    """A parent category renders a grid, not products; its children hold the bikes."""
    def handler(request: httpx.Request) -> httpx.Response:
        path = urlparse(str(request.url)).path
        if path == "/bikes/":
            return httpx.Response(200, json=tree("bikes/road", "bikes/workshop",
                                                 types={"bikes/workshop": "text"}))
        if path == "/bikes/road/":
            return httpx.Response(200, json=listing([make_product(pid=1)]))
        return httpx.Response(404, json={})

    bikes, _ = await scrape_lightspeed(make_config(), make_client(handler))

    assert [b.category for b in bikes] == ["Road"]
    # A "text" child is a CMS page (About Us, Workshop) and holds no products.
    assert not any("workshop" in b.product_url for b in bikes)


async def test_a_bike_in_two_categories_is_recorded_once():
    shared = make_product(pid=1, vid=10)

    def handler(request: httpx.Request) -> httpx.Response:
        path = urlparse(str(request.url)).path
        if path in ("/bikes/road/", "/bikes/gravel/"):
            return httpx.Response(200, json=listing([shared]))
        return httpx.Response(404, json={})

    bikes, _ = await scrape_lightspeed(
        make_config(collections=["bikes/road", "bikes/gravel"]), make_client(handler)
    )

    assert len(bikes) == 1
    # First category walked wins, so the category is stable run to run.
    assert bikes[0].category == "Road"


async def test_two_sizes_of_one_bike_are_both_kept():
    """Lightspeed lists each size as its own row; dedupe must not collapse them."""
    small = make_product(pid=1, vid=10, variant='"Size: 52"')
    large = make_product(pid=1, vid=11, variant='"Size: 58"')

    # Built by hand rather than with listing(), which keys rows by product id
    # and would therefore collapse these two into one before the pipeline sees
    # them, which is the very thing under test.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "shop": {"id": 1},
            "collection": {"count": 2, "pages": 1,
                           "products": {"a": small, "b": large}},
        })

    bikes, _ = await scrape_lightspeed(
        make_config(collections=["bikes/road"]), make_client(handler)
    )

    assert sorted(b.frame_size for b in bikes) == ["52", "58"]
