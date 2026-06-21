"""Registry loading and the Shopify collection->category override."""
import pytest

from scrapers.models import VendorConfig
from scrapers.pipelines import shopify as shopify_pipeline
from scrapers.pipelines.shopify import scrape_shopify
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
