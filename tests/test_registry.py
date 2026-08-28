"""Registry loading and the Shopify collection->category override."""
import pytest

from scrapers.models import VendorConfig
from scrapers.pipelines import shopify as shopify_pipeline
from scrapers.pipelines.shopify import _size_option_key, scrape_shopify
from scrapers.product_filter import drop_non_bikes
from scrapers.registry import load_registry


# --- registry -----------------------------------------------------------------

def test_registry_loads_every_vendor_into_vendorconfig():
    configs = load_registry()
    assert configs, "registry should not be empty"
    assert all(isinstance(c, VendorConfig) for c in configs)


def test_new_shopify_vendors_present_and_well_formed():
    by_name = {c.vendor_name: c for c in load_registry()}

    crooze = by_name["Crooze"]
    assert crooze.pipeline == "shopify"
    assert crooze.collection == "all-bikes"

    hendrys = by_name["Hendry's"]
    assert hendrys.pipeline == "shopify"
    # Hendry's relies on the collection->category override (generic product_type).
    assert hendrys.collection_category_map
    assert hendrys.collection_category_map["e-bikes"] == "E-Bike"
    # Every scraped collection must have a category mapping.
    assert set(hendrys.collections) <= set(hendrys.collection_category_map)


@pytest.mark.parametrize(
    "name",
    [
        "Woolys Wheels", "ABC Bikes", "CCACHE", "Giant Lygon St",
        "Giant South Yarra", "West Coast Cycles", "Treadly Bike Shop",
        "Cycle World", "Canberra Cyclery",
    ],
)
def test_added_vendor_is_registered_with_a_location(name):
    by_name = {c.vendor_name: c for c in load_registry()}
    config = by_name[name]
    assert config.city or config.cities
    assert config.category_map


def test_collection_category_maps_cover_every_scraped_collection():
    """A collection scraped but missing from collection_category_map silently
    falls back to category_map, which for these vendors means every product is
    dropped for having no category."""
    for config in load_registry():
        if not config.collection_category_map:
            continue
        assert set(config.collections or []) <= set(config.collection_category_map), (
            f"{config.vendor_name}: collections not covered by collection_category_map"
        )


# --- collection_category_map precedence ---------------------------------------

class _Resp:
    def __init__(self, payload):
        self._payload = payload
        self.headers = {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _product(product_type):
    return {
        "id": 100,
        "handle": "p1",
        "vendor": "Trek",
        "title": "Some Bike",
        "product_type": product_type,
        "tags": [],
        "images": [{"src": "https://x/i.jpg"}],
        "variants": [{"id": 1, "title": "M", "price": "1000", "available": True}],
    }


@pytest.fixture
def _patch_shopify(monkeypatch):
    async def _robots_ok(*a, **k):
        return True

    async def _no_sleep(*a, **k):
        return None

    monkeypatch.setattr(shopify_pipeline, "check_robots", _robots_ok)
    monkeypatch.setattr(shopify_pipeline.asyncio, "sleep", _no_sleep)


async def test_collection_category_map_overrides_product_type(_patch_shopify, monkeypatch):
    # product_type would resolve to Mountain, but the e-bikes collection wins.
    async def _fake_get(client, url, headers=None):
        return _Resp({"products": [_product("Mountain")]})

    monkeypatch.setattr(shopify_pipeline, "get_with_retry", _fake_get)

    config = VendorConfig(
        vendor_name="T", city="X", base_url="https://x", pipeline="shopify",
        category_map={"mountain": "Mountain"},
        collections=["e-bikes"],
        collection_category_map={"e-bikes": "E-Bike"},
    )
    bikes, _ = await scrape_shopify(config, client=None)
    assert len(bikes) == 1
    assert bikes[0].category == "E-Bike"


async def test_pagination_stops_when_page_adds_no_new_products(_patch_shopify, monkeypatch):
    # Simulate a collection whose since_id cursor loops: every page returns the
    # same full page of products. The scraper must stop instead of looping.
    monkeypatch.setattr(shopify_pipeline, "SHOPIFY_PAGE_SIZE", 2)
    page = {"products": [
        {**_product("Road Bikes"), "handle": "a"},
        {**_product("Road Bikes"), "handle": "b"},
    ]}
    calls = 0

    async def _fake_get(client, url, headers=None):
        nonlocal calls
        calls += 1
        return _Resp(page)

    monkeypatch.setattr(shopify_pipeline, "get_with_retry", _fake_get)

    config = VendorConfig(
        vendor_name="T", city="X", base_url="https://x", pipeline="shopify",
        category_map={"road bikes": "Road"}, collection="loopy",
    )
    bikes, _ = await scrape_shopify(config, client=None)
    # Page 1 ingests a + b (full page → continues); page 2 is all-seen → stop.
    assert calls == 2
    assert {b.product_url.split("/products/")[1].split("?")[0] for b in bikes} == {"a", "b"}


# --- frame size comes from the size axis, not the variant title ---------------

def _opts(*names):
    return [{"name": n, "position": i} for i, n in enumerate(names, start=1)]


@pytest.mark.parametrize(
    "names, expected",
    [
        (("Size",), "option1"),
        (("SIZE",), "option1"),
        (("Color", "Size"), "option2"),
        (("Colour", "Size", "Year"), "option2"),
        # An explicit frame-size axis beats a wheel-size one.
        (("FRAME SIZE", "WHEEL SIZE", "Color"), "option1"),
        # A loose match is accepted only when nothing better exists...
        (("SPEC", "Bike Size"), "option2"),
        # ...but a wheel size is never a frame size.
        (("WHEEL SIZE", "AXLE SPACING"), None),
        # No size axis at all: single-variant and colour-only products.
        (("Title",), None),
        (("Colour",), None),
    ],
)
def test_size_option_key(names, expected):
    assert _size_option_key({"options": _opts(*names)}) == expected


async def test_frame_size_reads_the_size_axis_not_the_colour(_patch_shopify, monkeypatch):
    product = {
        **_product("Road Bikes"),
        "options": _opts("Colour", "Size"),
        "variants": [
            {"id": 1, "title": "Forge Grey / M", "option1": "Forge Grey",
             "option2": "M", "price": "1000", "available": True},
        ],
    }

    async def _fake_get(client, url, headers=None):
        return _Resp({"products": [product]})

    monkeypatch.setattr(shopify_pipeline, "get_with_retry", _fake_get)

    config = VendorConfig(
        vendor_name="T", city="X", base_url="https://x", pipeline="shopify",
        category_map={"road bikes": "Road"}, collection="all-bikes",
    )
    bikes, _ = await scrape_shopify(config, client=None)
    assert [b.frame_size for b in bikes] == ["M"]


async def test_colour_only_product_is_kept_with_unknown_frame_size(
    _patch_shopify, monkeypatch
):
    """"Forge Grey" and "Banksia Orange" share no word with the colour
    vocabulary, so title parsing recorded them as frame sizes. With no size
    axis the size is unknown — but the bike is still real and must be kept."""
    product = {
        **_product("Road Bikes"),
        "options": _opts("Colour"),
        "variants": [
            {"id": 1, "title": "Forge Grey", "option1": "Forge Grey",
             "price": "1000", "available": True},
            {"id": 2, "title": "Banksia Orange", "option1": "Banksia Orange",
             "price": "1100", "available": True},
        ],
    }

    async def _fake_get(client, url, headers=None):
        return _Resp({"products": [product]})

    monkeypatch.setattr(shopify_pipeline, "get_with_retry", _fake_get)

    config = VendorConfig(
        vendor_name="T", city="X", base_url="https://x", pipeline="shopify",
        category_map={"road bikes": "Road"}, collection="all-bikes",
    )
    bikes, _ = await scrape_shopify(config, client=None)
    assert [b.frame_size for b in bikes] == ["N/A", "N/A"]
    assert len({b.id for b in bikes}) == 2


async def test_framesets_and_scooters_are_not_bikes(_patch_shopify, monkeypatch):
    """Shops file both under a bike product_type, so only the title tells."""
    products = [
        {**_product("Road Race Bikes"), "handle": "a",
         "title": "Safi Works Form R32.1 Road Frameset"},
        {**_product("Childrens Bikes & Scooters"), "handle": "b",
         "title": "Micro Sprite Scooter"},
        {**_product("Road Race Bikes"), "handle": "c", "title": "Factor Ostro VAM"},
    ]

    async def _fake_get(client, url, headers=None):
        return _Resp({"products": products})

    monkeypatch.setattr(shopify_pipeline, "get_with_retry", _fake_get)

    config = VendorConfig(
        vendor_name="T", city="X", base_url="https://x", pipeline="shopify",
        category_map={"road race bikes": "Road", "childrens bikes & scooters": "Commuter"},
        collection="all-bikes",
    )
    # The scooter goes on product_type, which the pipeline still screens. The
    # frameset's product_type is "Road Race Bikes" — only its title gives it
    # away — and title screening now lives in the shared gate at the
    # orchestrator, so this asserts against the boundary production uses.
    bikes, _ = await scrape_shopify(config, client=None)
    assert [b.model_name for b in bikes] == [
        "Safi Works Form R32.1 Road Frameset",
        "Factor Ostro VAM",
    ]

    kept, rejected = drop_non_bikes(bikes)
    assert [b.model_name for b in kept] == ["Factor Ostro VAM"]
    assert rejected == {"accessory:frameset": 1}


async def test_collection_pagination_uses_page_not_since_id(_patch_shopify, monkeypatch):
    """Collection endpoints ignore since_id, so paging with it truncated every
    collection at one page."""
    monkeypatch.setattr(shopify_pipeline, "SHOPIFY_PAGE_SIZE", 2)
    pages = {
        1: [{**_product("Road Bikes"), "handle": "a"}, {**_product("Road Bikes"), "handle": "b"}],
        2: [{**_product("Road Bikes"), "handle": "c"}],
    }
    requested = []

    async def _fake_get(client, url, headers=None):
        requested.append(url)
        page = 2 if "page=2" in url else 1
        return _Resp({"products": pages[page]})

    monkeypatch.setattr(shopify_pipeline, "get_with_retry", _fake_get)

    config = VendorConfig(
        vendor_name="T", city="X", base_url="https://x", pipeline="shopify",
        category_map={"road bikes": "Road"}, collection="bikes",
    )
    bikes, _ = await scrape_shopify(config, client=None)
    assert not any("since_id" in u for u in requested)
    assert len(bikes) == 3


async def test_root_products_json_still_pages_with_since_id(_patch_shopify, monkeypatch):
    monkeypatch.setattr(shopify_pipeline, "SHOPIFY_PAGE_SIZE", 2)
    pages = [
        [{**_product("Road Bikes"), "handle": "a"}, {**_product("Road Bikes"), "handle": "b"}],
        [{**_product("Road Bikes"), "handle": "c"}],
    ]
    requested = []

    async def _fake_get(client, url, headers=None):
        requested.append(url)
        return _Resp({"products": pages[min(len(requested) - 1, 1)]})

    monkeypatch.setattr(shopify_pipeline, "get_with_retry", _fake_get)

    config = VendorConfig(
        vendor_name="T", city="X", base_url="https://x", pipeline="shopify",
        category_map={"road bikes": "Road"},
    )
    await scrape_shopify(config, client=None)
    assert any("since_id" in u for u in requested)


async def test_category_map_still_used_without_collection_override(_patch_shopify, monkeypatch):
    async def _fake_get(client, url, headers=None):
        return _Resp({"products": [_product("Gravel Bikes")]})

    monkeypatch.setattr(shopify_pipeline, "get_with_retry", _fake_get)

    config = VendorConfig(
        vendor_name="T", city="X", base_url="https://x", pipeline="shopify",
        category_map={"gravel bikes": "Gravel"},
        collection="all-bikes",
    )
    bikes, _ = await scrape_shopify(config, client=None)
    assert len(bikes) == 1
    assert bikes[0].category == "Gravel"


def test_vendors_are_opted_in_to_instagram_unless_they_say_otherwise():
    """The daily Instagram post reads this flag (social/select.py). Defaulting
    it to True keeps existing vendor files valid without an edit; a shop that
    objects to its photos being reposted sets `instagram: false`."""
    configs = load_registry()
    assert configs, "registry should not be empty"
    assert all(isinstance(config.instagram, bool) for config in configs)
    assert any(config.instagram for config in configs)
