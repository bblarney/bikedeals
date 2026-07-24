"""Unit tests for the pure scraper helpers and the retry wrapper."""
import httpx
import pytest

from scrapers.models import BikeRecord, compute_discount, make_bike_id
from scrapers.utils import (
    CloudflareChallenge,
    _apply_proxy,
    extract_frame_size,
    get_with_retry,
    parse_drivetrain_groupset,
    parse_frame_material,
    parse_price,
    resolve_category,
)


# --- compute_discount ---------------------------------------------------------

def test_compute_discount_normal():
    assert compute_discount(750, 1000) == 25


@pytest.mark.parametrize("sale,original", [(1000, None), (1000, 0), (1000, 1000), (1200, 1000)])
def test_compute_discount_no_or_invalid_discount(sale, original):
    assert compute_discount(sale, original) == 0


# --- make_bike_id -------------------------------------------------------------

def test_make_bike_id_is_deterministic():
    a = make_bike_id("Vendor", "https://x/p", "M", "Sydney")
    b = make_bike_id("Vendor", "https://x/p", "M", "Sydney")
    assert a == b and len(a) == 16


def test_make_bike_id_varies_by_city():
    syd = make_bike_id("Vendor", "https://x/p", "M", "Sydney")
    mel = make_bike_id("Vendor", "https://x/p", "M", "Melbourne")
    assert syd != mel


# --- parse_price --------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("$1,299.00", 1299.00),
    ("1499", 1499.0),
    ("From $899", 899.0),
    ("", None),
    (None, None),
    ("Call for price", None),
])
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


# --- extract_frame_size -------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Small / Red", "Small"),
    ("54cm", "54cm"),
    ("M", "M"),
    ("Matte Black", "Matte Black"),  # no size segment -> returns original
])
def test_extract_frame_size(raw, expected):
    assert extract_frame_size(raw) == expected


# --- resolve_category ---------------------------------------------------------

def test_resolve_category_exact_match():
    cmap = {"road bikes": "Road", "mountain bikes": "Mountain"}
    assert resolve_category(["road bikes"], cmap) == "Road"


def test_resolve_category_substring_longest_wins():
    # Both "bikes" and "mountain bikes" are substrings; longest key wins.
    cmap = {"bikes": "Road", "mountain bikes": "Mountain"}
    assert resolve_category(["all mountain bikes on sale"], cmap) == "Mountain"


def test_resolve_category_no_match_returns_none():
    assert resolve_category(["accessories"], {"road bikes": "Road"}) is None


# --- body-html parsers --------------------------------------------------------

def test_parse_frame_material():
    assert parse_frame_material("<p>Full <b>carbon</b> frame</p>") == "Carbon"
    assert parse_frame_material("<p>6061 aluminium</p>") == "Aluminium"
    assert parse_frame_material(None) is None


def test_parse_drivetrain_groupset():
    assert parse_drivetrain_groupset("Shimano 105 groupset") == "Shimano 105"
    # The regex captures one trailing qualifier token after the tier.
    assert parse_drivetrain_groupset("SRAM Rival AXS") == "SRAM Rival AXS"
    assert parse_drivetrain_groupset("no groupset mentioned") is None


# --- BikeRecord validation ----------------------------------------------------

def _record(**kw):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    base = dict(
        id="x", vendor_name="V", city=None, brand="B", model_name="M",
        category="Road", frame_size="M", price_original=1000.0, price_sale=800.0,
        discount_percentage=20, in_stock=True, product_url="https://x/p",
        image_url=None, scraped_at=now, last_seen_at=now,
    )
    base.update(kw)
    return BikeRecord(**base)


def test_bikerecord_rejects_sale_above_original():
    with pytest.raises(ValueError):
        _record(price_sale=1200.0, price_original=1000.0)


def test_bikerecord_rejects_bad_category():
    with pytest.raises(ValueError):
        _record(category="Unicycle")


# --- get_with_retry -----------------------------------------------------------

class _FakeResp:
    def __init__(self, status_code=200, headers=None):
        self.status_code = status_code
        self.request = None  # get_with_retry references resp.request on retryable status
        self.headers = headers or {}


class _FlakyClient:
    """Fails `fail_times` with a transport error, then returns 200."""
    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = 0

    async def get(self, url, headers=None, follow_redirects=True):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise httpx.ConnectError("boom")
        return _FakeResp(200)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _instant(_seconds):
        return None
    monkeypatch.setattr("scrapers.utils.asyncio.sleep", _instant)


async def test_get_with_retry_succeeds_after_transient_failures():
    client = _FlakyClient(fail_times=2)
    resp = await get_with_retry(client, "https://x", retries=3)
    assert resp.status_code == 200
    assert client.calls == 3


async def test_get_with_retry_raises_after_exhausting_retries():
    client = _FlakyClient(fail_times=5)
    with pytest.raises(httpx.ConnectError):
        await get_with_retry(client, "https://x", retries=3)
    assert client.calls == 3


async def test_get_with_retry_retries_on_5xx_status():
    class _ServerErrorClient:
        def __init__(self):
            self.calls = 0

        async def get(self, url, headers=None, follow_redirects=True):
            self.calls += 1
            return _FakeResp(503 if self.calls < 3 else 200)

    client = _ServerErrorClient()
    resp = await get_with_retry(client, "https://x", retries=3)
    assert resp.status_code == 200
    assert client.calls == 3


async def test_get_with_retry_fails_fast_on_cloudflare_challenge():
    """A Cloudflare bot challenge isn't transient: raise immediately, no retries."""
    class _ChallengeClient:
        def __init__(self):
            self.calls = 0

        async def get(self, url, headers=None, follow_redirects=True):
            self.calls += 1
            return _FakeResp(429, headers={"cf-mitigated": "challenge"})

    client = _ChallengeClient()
    with pytest.raises(CloudflareChallenge):
        await get_with_retry(client, "https://x", retries=3)
    assert client.calls == 1  # not retried


# --- proxy routing ------------------------------------------------------------

def test_apply_proxy_noop_when_unset(monkeypatch):
    """With no proxy configured, the request is returned unchanged."""
    monkeypatch.setattr("scrapers.utils.SCRAPER_PROXY_URL", None)
    url, headers = _apply_proxy("https://shop.example/products.json", {"User-Agent": "UA"})
    assert url == "https://shop.example/products.json"
    assert headers == {"User-Agent": "UA"}


def test_apply_proxy_rewrites_when_set(monkeypatch):
    """With a proxy configured, the target moves to X-Target-URL, the token is
    attached, and the caller's own headers (User-Agent) are preserved."""
    monkeypatch.setattr("scrapers.utils.SCRAPER_PROXY_URL", "https://proxy.workers.dev")
    monkeypatch.setattr("scrapers.utils.SCRAPER_PROXY_TOKEN", "secret-token")
    url, headers = _apply_proxy("https://shop.example/products.json", {"User-Agent": "UA"})
    assert url == "https://proxy.workers.dev"
    assert headers == {
        "User-Agent": "UA",
        "X-Target-URL": "https://shop.example/products.json",
        "X-Proxy-Token": "secret-token",
    }


async def test_get_with_retry_routes_through_proxy(monkeypatch):
    """get_with_retry issues the actual GET against the proxy URL, carrying the
    real target in X-Target-URL, when a proxy is configured."""
    monkeypatch.setattr("scrapers.utils.SCRAPER_PROXY_URL", "https://proxy.workers.dev")
    monkeypatch.setattr("scrapers.utils.SCRAPER_PROXY_TOKEN", "secret-token")

    seen = {}

    class _CapturingClient:
        async def get(self, url, headers=None, follow_redirects=True):
            seen["url"] = url
            seen["headers"] = headers
            return _FakeResp(200)

    resp = await get_with_retry(
        _CapturingClient(), "https://shop.example/products.json", headers={"User-Agent": "UA"}
    )
    assert resp.status_code == 200
    assert seen["url"] == "https://proxy.workers.dev"
    assert seen["headers"]["X-Target-URL"] == "https://shop.example/products.json"
    assert seen["headers"]["X-Proxy-Token"] == "secret-token"
    assert seen["headers"]["User-Agent"] == "UA"
