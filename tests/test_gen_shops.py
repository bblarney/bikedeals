"""The generated shop list must stay in step with the vendor registry.

frontend/src/content/shops.js is committed, not built on demand: prerender.js
reads it offline to decide which shop pages exist. So a vendor added to
scrapers/vendors/ without regenerating ships a shop that has no page, and a
vendor removed leaves a page that 404s on its own data. This test is what makes
that a failing build rather than a quiet gap.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from scrapers.registry import load_registry
from scrapers.utils import vendor_slug

ROOT = Path(__file__).resolve().parent.parent
SHOPS_JS = ROOT / "frontend" / "src" / "content" / "shops.js"


def _gen_shops():
    spec = importlib.util.spec_from_file_location("gen_shops", ROOT / "scripts" / "gen_shops.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen_shops"] = module
    spec.loader.exec_module(module)
    return module


def test_committed_shops_js_matches_the_registry():
    generated = _gen_shops().build()
    current = SHOPS_JS.read_text(encoding="utf-8")
    assert current == generated, (
        "frontend/src/content/shops.js is stale. Run: python scripts/gen_shops.py"
    )


def test_every_vendor_has_a_unique_slug():
    slugs = {}
    for cfg in load_registry():
        slug = vendor_slug(cfg.vendor_name)
        assert slug, f"{cfg.vendor_name!r} produces an empty slug"
        assert slug not in slugs, (
            f"{cfg.vendor_name!r} and {slugs[slug]!r} both slug to {slug!r}"
        )
        slugs[slug] = cfg.vendor_name


@pytest.mark.parametrize(
    "name,expected",
    [
        ("99 Bikes", "99-bikes"),
        ("Bike Zone Fitzroy", "bike-zone-fitzroy"),
        ("Bikes.com.au", "bikes-com-au"),
        # Punctuation collapses rather than leaving a doubled or trailing dash.
        ("De Grandi Cycle Works ", "de-grandi-cycle-works"),
        ("Ride & Roll", "ride-roll"),
        # ASCII-folded, so an accented name does not become a percent-encoded URL.
        ("Cervélo Store", "cervelo-store"),
    ],
)
def test_vendor_slug_rules(name, expected):
    assert vendor_slug(name) == expected


def test_shops_js_is_loadable_by_bare_node():
    """prerender.js imports this file outside Vite, so it must stay plain JS."""
    source = SHOPS_JS.read_text(encoding="utf-8")
    # The header comment names the things being banned, so check the code only.
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("//")
    )
    assert "import " not in code, "shops.js must not import anything"
    assert "import.meta" not in code, "shops.js must not read import.meta.env"
    assert "SHOP_PATHS" in code
