"""Unit tests for the headless Next.js / Ecwid pipeline."""
from datetime import datetime, timezone

import pytest

from scrapers.models import VendorConfig
from scrapers.pipelines import ecwid_next as pipeline
from scrapers.pipelines.ecwid_next import (
    _build_records,
    _catalogue_from_js,
    _category_candidates,
    _in_scope,
    _known_brands,
    _resolve_brand,
    _slugify,
    scrape_ecwid_next,
)

NOW = datetime(2026, 8, 11, tzinfo=timezone.utc)


def make_config(**overrides) -> VendorConfig:
    base = dict(
        vendor_name="Test Shop",
        city="Sydney",
        base_url="https://shop.example",
        pipeline="ecwid_next",
        shop_path="bikes",
        collections=["Bikes"],
        category_map={
            "e bikes": "E-Bike",
            "mountain bikes": "Mountain",
            "road bikes": "Road",
            "kids bikes": "Commuter",
        },
    )
    base.update(overrides)
    return VendorConfig(**base)


def make_product(**overrides) -> dict:
    base = {
        "id": 1,
        "sku": "17640 - Base",
        "name": "Norco Fluid A3",
        "price": 2999,
        "compareToPrice": None,
        "inStock": True,
        "enabled": True,
        "brand": "Norco",
        "imageUrl": "https://cdn.example/fluid.jpg",
        "suggestedCategory": "Bikes / Mountain Bikes / Dual Suspension",
        "categoryPaths": ["Bikes", "Bikes / Mountain Bikes",
                          "Bikes / Mountain Bikes / Dual Suspension"],
    }
    base.update(overrides)
    return base


def chunk_js(json_text: str) -> str:
    """A build chunk shaped like the real one: JSON inside a JS string literal."""
    escaped = json_text.replace("\\", "\\\\").replace("'", "\\'")
    return f"globalThis.TURBOPACK.push([null,212251,e=>{{e.v(JSON.parse('{escaped}'))}}]);"


# --- catalogue extraction -----------------------------------------------------

def test_catalogue_from_js_unwraps_the_json_parse_literal():
    js = chunk_js('[{"id":1,"name":"Norco Fluid A3","categoryPaths":["Bikes"]}]')
    assert _catalogue_from_js(js) == [
        {"id": 1, "name": "Norco Fluid A3", "categoryPaths": ["Bikes"]}
    ]


def test_catalogue_from_js_handles_escaped_apostrophes():
    """Names like "Children's Bike Helmet" arrive as \\' inside the JS literal."""
    js = chunk_js('[{"name":"Trek Children\'s Bike","categoryPaths":["Bikes"]}]')
    assert _catalogue_from_js(js)[0]["name"] == "Trek Children's Bike"


def test_catalogue_from_js_skips_literals_without_the_marker():
    js = chunk_js('["not","the","catalogue"]') + chunk_js('[{"categoryPaths":["Bikes"]}]')
    assert _catalogue_from_js(js) == [{"categoryPaths": ["Bikes"]}]


def test_catalogue_from_js_returns_empty_when_absent():
    assert _catalogue_from_js("console.log('hello')") == []


# --- slugs --------------------------------------------------------------------

@pytest.mark.parametrize(
    "name, slug",
    [
        ("Norco Fluid A3", "norco-fluid-a3"),
        ("Trek FX+ LT Cross bar", "trek-fx-lt-cross-bar"),
        ("Factor MONZA - SRAM Force w/ Power Meter", "factor-monza-sram-force-w-power-meter"),
        ('Base Bike 24"', "base-bike-24"),
    ],
)
def test_slugify_matches_the_storefronts_urls(name, slug):
    assert _slugify(name) == slug


# --- scope and categories -----------------------------------------------------

def test_in_scope_keeps_only_the_configured_root_categories():
    assert _in_scope(make_product(), ["Bikes"])
    helmet = make_product(categoryPaths=["Helmets", "Helmets / MTB Helmets"])
    assert not _in_scope(helmet, ["Bikes"])


def test_in_scope_without_collections_keeps_everything():
    assert _in_scope(make_product(categoryPaths=["Helmets"]), None)


def test_category_candidates_put_electric_paths_first():
    """An e-MTB sits under both E Bikes and MTB; electric has to win."""
    product = make_product(
        suggestedCategory="Bikes / E Bikes / E MTB Bikes",
        categoryPaths=["Bikes", "Bikes / Mountain Bikes", "Bikes / E Bikes",
                       "Bikes / E Bikes / E MTB Bikes"],
    )
    candidates = _category_candidates(product)
    assert candidates[0].startswith("bikes / e bikes")
    assert all("mountain" not in c for c in candidates[:2])


def test_e_mtb_resolves_to_ebike_not_mountain():
    product = make_product(
        name="Trek Marlin+ 8 E MTB",
        suggestedCategory="Bikes / E Bikes / E MTB Bikes",
        categoryPaths=["Bikes", "Bikes / Mountain Bikes", "Bikes / E Bikes / E MTB Bikes"],
    )
    bikes, _, _, _ = _build_records(
        make_config(), [product], {"trek-marlin-8-e-mtb"}, NOW
    )
    assert [b.category for b in bikes] == ["E-Bike"]


# --- brands -------------------------------------------------------------------

def test_known_brands_include_brand_map_keys():
    products = [make_product(brand="Norco"), make_product(brand=None)]
    config = make_config(brand_map={"hornit": "Hornit"})
    assert _known_brands(products, config) == ["hornit", "Norco"]


def test_brand_falls_back_to_a_name_match_not_the_shop_name():
    """A third of entries leave `brand` null; "Cranks" must not become a brand."""
    config = make_config(brand_map={"hornit": "Hornit"})
    products = [make_product(name="Hornit AIRO 14 inch Balance Bike", brand=None)]
    assert _resolve_brand(products[0], _known_brands(products, config), config) == "Hornit"


def test_brand_falls_back_to_the_shop_name_when_nothing_matches():
    config = make_config()
    product = make_product(name="Mystery Bike", brand=None)
    assert _resolve_brand(product, _known_brands([product], config), config) == "Test Shop"


# --- record building ----------------------------------------------------------

def test_build_records_maps_a_product_onto_the_schema():
    bikes, invalid, skipped, url_skipped = _build_records(
        make_config(), [make_product()], {"norco-fluid-a3"}, NOW
    )
    assert (invalid, skipped, url_skipped) == (0, 0, 0)
    bike = bikes[0]
    assert bike.brand == "Norco"
    assert bike.category == "Mountain"
    assert bike.price_sale == 2999.0
    assert bike.price_original is None
    assert bike.discount_percentage == 0
    assert bike.in_stock
    assert bike.frame_size == "One Size"
    assert bike.product_url == "https://shop.example/product/norco-fluid-a3"
    assert bike.image_url == "https://cdn.example/fluid.jpg"
    # The shop's POS id is not a manufacturer part number: recording it would
    # cross-match unrelated shops' internal ids.
    assert bike.sku is None


def test_build_records_computes_the_discount():
    product = make_product(price=2499, compareToPrice=2999)
    bikes, _, _, _ = _build_records(make_config(), [product], {"norco-fluid-a3"}, NOW)
    assert bikes[0].price_original == 2999.0
    assert bikes[0].discount_percentage == 17


def test_build_records_drops_a_compare_price_that_is_not_a_discount():
    product = make_product(price=2999, compareToPrice=2999)
    bikes, _, _, _ = _build_records(make_config(), [product], {"norco-fluid-a3"}, NOW)
    assert bikes[0].price_original is None


def test_build_records_skips_unpublished_products():
    product = make_product(enabled=False)
    bikes, _, _, _ = _build_records(make_config(), [product], {"norco-fluid-a3"}, NOW)
    assert bikes == []


def test_build_records_skips_products_with_no_public_page():
    """No sitemap entry means the URL would 404, so the row is worthless."""
    bikes, _, _, url_skipped = _build_records(make_config(), [make_product()], set(), NOW)
    assert bikes == []
    assert url_skipped == 1


def test_build_records_skips_accessories_by_root_category():
    helmet = make_product(
        name="Kask Mojito 3 Road Helmet",
        categoryPaths=["Helmets", "Helmets / Road Helmets"],
        suggestedCategory="Helmets / Road Helmets",
    )
    bikes, _, _, _ = _build_records(
        make_config(), [helmet], {"kask-mojito-3-road-helmet"}, NOW
    )
    assert bikes == []


def test_build_records_skips_products_without_a_price():
    product = make_product(price=None)
    bikes, _, _, _ = _build_records(make_config(), [product], {"norco-fluid-a3"}, NOW)
    assert bikes == []


# --- end to end ---------------------------------------------------------------

class _Resp:
    def __init__(self, text):
        self.text = text
        self.headers = {}

    def raise_for_status(self):
        pass


@pytest.fixture
def _patch_pipeline(monkeypatch):
    async def _robots_ok(*a, **k):
        return True

    async def _no_sleep(*a, **k):
        return None

    monkeypatch.setattr(pipeline, "check_robots", _robots_ok)
    monkeypatch.setattr(pipeline.asyncio, "sleep", _no_sleep)


async def test_scrape_finds_the_catalogue_chunk_and_the_sitemap(_patch_pipeline, monkeypatch):
    catalogue = chunk_js(
        '[{"id":1,"name":"Norco Fluid A3","price":2999,"compareToPrice":null,'
        '"inStock":true,"enabled":true,"brand":"Norco","imageUrl":"https://cdn/x.jpg",'
        '"suggestedCategory":"Bikes / Mountain Bikes",'
        '"categoryPaths":["Bikes","Bikes / Mountain Bikes"]}]'
    )
    pages = {
        "https://shop.example/bikes": (
            '<script src="/_next/static/chunks/aaa.js"></script>'
            '<script src="/_next/static/chunks/bbb.js"></script>'
        ),
        "https://shop.example/_next/static/chunks/aaa.js": "console.log(1)",
        "https://shop.example/_next/static/chunks/bbb.js": catalogue,
        "https://shop.example/sitemap.xml": (
            "<urlset><url><loc>https://shop.example/bikes</loc></url>"
            "<url><loc>https://shop.example/product/norco-fluid-a3</loc></url></urlset>"
        ),
    }
    requested = []

    async def _fake_get(client, url, headers=None):
        requested.append(url)
        return _Resp(pages[url])

    monkeypatch.setattr(pipeline, "get_with_retry", _fake_get)

    bikes, invalid = await scrape_ecwid_next(make_config(), client=None)
    assert invalid == 0
    assert [b.model_name for b in bikes] == ["Norco Fluid A3"]
    assert bikes[0].product_url == "https://shop.example/product/norco-fluid-a3"
    # The catalogue is in the last-referenced chunk, so the scan starts there and
    # never fetches the earlier ones.
    assert "https://shop.example/_next/static/chunks/aaa.js" not in requested


async def test_scrape_returns_empty_when_the_bundle_stops_carrying_products(
    _patch_pipeline, monkeypatch
):
    """A redesign that moves the catalogue out of the bundle must fail as an
    empty scrape (data preserved), not raise or invent rows."""
    pages = {
        "https://shop.example/bikes": '<script src="/_next/static/chunks/aaa.js"></script>',
        "https://shop.example/_next/static/chunks/aaa.js": "console.log(1)",
    }

    async def _fake_get(client, url, headers=None):
        return _Resp(pages[url])

    monkeypatch.setattr(pipeline, "get_with_retry", _fake_get)

    bikes, invalid = await scrape_ecwid_next(make_config(), client=None)
    assert (bikes, invalid) == ([], 0)
