"""Pagination tests for the Shopify pipeline's two cursoring modes.

The failure these guard against is silent: a shop that ignores the cursor
re-serves page one, the "added no new products" guard reads that as the end of
the catalogue, and the vendor lands with 250 products, no error, and a
scrape_check PASS. Freedom Machine (1,260 products) is the live example.
"""
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from scrapers.models import VendorConfig
from scrapers.pipelines import shopify as shopify_module
from scrapers.pipelines.shopify import _scrape_collection

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)
PAGE_SIZE = 250


@pytest.fixture(autouse=True)
def _no_delay(monkeypatch):
    """Strip the politeness sleep so these tests don't take a minute each."""
    monkeypatch.setattr(shopify_module, "SCRAPER_DELAY_RANGE", (0.0, 0.0))


def make_config(**overrides) -> VendorConfig:
    base = dict(
        vendor_name="Test Shop",
        city="Byron Bay",
        base_url="https://shop.example",
        pipeline="shopify",
        category_map={"road": "Road"},
    )
    base.update(overrides)
    return VendorConfig(**base)


def make_product(index: int) -> dict:
    """One well-formed Shopify product that the pipeline will keep."""
    return {
        "id": index,
        "handle": f"bike-{index}",
        "title": f"Test Road Bike {index}",
        "vendor": "Bianchi",
        "product_type": "Road",
        "tags": [],
        "images": [{"src": "https://shop.example/bike.jpg"}],
        "options": [{"name": "Frame Size", "position": 1}],
        "variants": [
            {"id": index * 10, "option1": "56", "price": "2999.00",
             "compare_at_price": "3999.00", "available": True, "sku": f"SKU{index}"}
        ],
    }


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_root_endpoint_falls_back_to_page_when_since_id_is_ignored():
    """A shop that ignores since_id must still be paged to exhaustion.

    The shop serves 600 products: it honours ?page=N and ignores since_id,
    re-serving page one for any since_id request.
    """
    catalogue = [make_product(i) for i in range(1, 601)]
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        params = parse_qs(urlparse(str(request.url)).query)
        if "page" in params:
            page = int(params["page"][0])
        else:
            # No page param: page one, whether or not since_id was sent.
            page = 1
        start = (page - 1) * PAGE_SIZE
        return httpx.Response(200, json={"products": catalogue[start:start + PAGE_SIZE]})

    bikes, _, invalid = await _scrape_collection(
        make_config(), make_client(handler), None, set(), NOW
    )

    assert invalid == 0
    assert len(bikes) == 600, "every product should be reached via the ?page= fallback"
    assert {b.model_name for b in bikes} == {p["title"] for p in catalogue}
    # The fallback must resume at page 2, not re-fetch page 1 or skip to page 3.
    assert any("page=2" in url for url in requests)
    assert any("page=3" in url for url in requests)


async def test_root_endpoint_uses_since_id_while_it_works():
    """The fallback must not disturb shops whose since_id cursoring is fine."""
    catalogue = [make_product(i) for i in range(1, 501)]
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        params = parse_qs(urlparse(str(request.url)).query)
        since = int(params.get("since_id", ["0"])[0])
        remaining = [p for p in catalogue if p["id"] > since]
        return httpx.Response(200, json={"products": remaining[:PAGE_SIZE]})

    bikes, _, _ = await _scrape_collection(
        make_config(), make_client(handler), None, set(), NOW
    )

    assert len(bikes) == 500
    assert not any("page=" in url for url in requests), "since_id worked; no fallback needed"


async def test_exhausted_catalogue_still_stops():
    """A genuinely finished catalogue must not loop, even with the fallback.

    The shop honours neither cursor and always returns the same single page, so
    the fallback fires once and then the run has to stop.
    """
    catalogue = [make_product(i) for i in range(1, 251)]
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"products": catalogue})

    bikes, _, _ = await _scrape_collection(
        make_config(), make_client(handler), None, set(), NOW
    )

    assert len(bikes) == 250, "products are recorded once, not duplicated"
    assert calls == 3, "page 1, the since_id repeat, then one ?page=2 probe"


async def test_collection_endpoint_pages_without_the_root_fallback():
    """Collections already cursor on ?page=N and must not take the root path."""
    catalogue = [make_product(i) for i in range(1, 501)]
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        params = parse_qs(urlparse(str(request.url)).query)
        page = int(params.get("page", ["1"])[0])
        start = (page - 1) * PAGE_SIZE
        return httpx.Response(200, json={"products": catalogue[start:start + PAGE_SIZE]})

    bikes, _, _ = await _scrape_collection(
        make_config(), make_client(handler), "bikes", set(), NOW
    )

    assert len(bikes) == 500
    assert all("/collections/bikes/products.json" in url for url in requests)
    assert not any("since_id" in url for url in requests)
