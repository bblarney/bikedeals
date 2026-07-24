import asyncio
import logging
import random
import re
from urllib import robotparser
from urllib.parse import urljoin

_HTML_TAG_RE = re.compile(r"<[^>]+>")

_FRAME_MATERIAL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bcarbon(?:\s+fi(?:bre|er))?\b", re.IGNORECASE), "Carbon"),
    (re.compile(r"\btitanium\b|\bti\s+frame\b", re.IGNORECASE), "Titanium"),
    (re.compile(r"\bsteel\b|\bchromoly\b|\bcr[- ]mo\b|\bcro[- ]mo\b", re.IGNORECASE), "Steel"),
    (re.compile(r"\balumini?um\b|\balloy\b", re.IGNORECASE), "Aluminium"),
]

_GROUPSET_RE = re.compile(
    r"(Shimano\s+(?:Dura[\s\-]?Ace|Ultegra|105|Tiagra|Sora|Claris|XTR|Deore\s+XT|XT|SLX|Deore|Alivio|Acera|Altus|GRX|CUES)(?:\s+Di2)?"
    r"|SRAM\s+(?:Red|Force|Rival|Apex|XX1?|X01|GX|NX|SX)(?:\s+(?:Eagle|AXS|XPLR|eTap))?"
    r"|Campagnolo\s+(?:Super\s+Record|Record|Chorus|Potenza|Centaur))",
    re.IGNORECASE,
)

_GROUPSET_BRAND_CASE = {
    "shimano": "Shimano",
    "sram": "SRAM",
    "campagnolo": "Campagnolo",
}
_GROUPSET_WORD_CASE = {
    # Shimano
    "di2": "Di2",
    "xtr": "XTR",
    "xt": "XT",
    "slx": "SLX",
    "grx": "GRX",
    "cues": "CUES",
    "dura-ace": "Dura-Ace",
    # SRAM
    "axs": "AXS",
    "xplr": "XPLR",
    "xx1": "XX1",
    "xx": "XX",
    "x01": "X01",
    "gx": "GX",
    "nx": "NX",
    "sx": "SX",
    "etap": "eTap",
}


def _normalise_groupset(raw: str) -> str:
    words = raw.split()
    result = []
    for i, w in enumerate(words):
        key = w.lower()
        if i == 0:
            result.append(_GROUPSET_BRAND_CASE.get(key, w.title()))
        else:
            result.append(_GROUPSET_WORD_CASE.get(key, w.title()))
    return " ".join(result)


def parse_frame_material(body_html: str | None) -> str | None:
    if not body_html:
        return None
    text = _HTML_TAG_RE.sub(" ", body_html)
    for pattern, label in _FRAME_MATERIAL_PATTERNS:
        if pattern.search(text):
            return label
    return None


def parse_drivetrain_groupset(body_html: str | None) -> str | None:
    if not body_html:
        return None
    text = _HTML_TAG_RE.sub(" ", body_html)
    m = _GROUPSET_RE.search(text)
    return _normalise_groupset(m.group(1)) if m else None


_SIZE_WORD_RE = re.compile(
    r"^(XXS|XS|S|M|L|XL|XXL|XXXL|3XL|4XL"
    r"|X-?Small|Small|Medium|Large|X-?Large|XX-?Large|Extra\s*Large"
    r"|[SMLX][0-9]|[0-9][SMLX]"
    r")$",
    re.IGNORECASE,
)
_SIZE_MEAS_RE = re.compile(
    r'^[0-9]{2,3}(?:\.[05])?(?:"|cm)?$',
    re.IGNORECASE,
)

import httpx

from scrapers.config import SCRAPER_PROXY_TOKEN, SCRAPER_PROXY_URL

logger = logging.getLogger(__name__)


# Paths we might fetch from any vendor. If robots.txt disallows any of them
# for our user agent, we skip the whole vendor.
_PATHS_TO_CHECK = ("/", "/products.json", "/products")


def _apply_proxy(url: str, headers: dict | None) -> tuple[str, dict | None]:
    """Rewrite a request to go through the Cloudflare Worker proxy, if configured.

    GitHub Actions egresses from a datacenter IP range that Cloudflare/Shopify
    block as a class, so in CI every vendor request is tunnelled through a free
    Worker (see worker/README.md) that re-issues it from a Cloudflare IP. The
    target URL travels in ``X-Target-URL`` and the shared secret in
    ``X-Proxy-Token``; the caller's other headers (notably our User-Agent) are
    preserved and forwarded by the Worker.

    When ``SCRAPER_PROXY_URL`` is unset (local dev, tests) this is a no-op, so
    the direct-request behaviour and all existing tests are unchanged.
    """
    if not SCRAPER_PROXY_URL:
        return url, headers
    proxied = dict(headers or {})
    proxied["X-Target-URL"] = url
    if SCRAPER_PROXY_TOKEN:
        proxied["X-Proxy-Token"] = SCRAPER_PROXY_TOKEN
    return SCRAPER_PROXY_URL, proxied

# Match the User-Agent header we send (case-insensitive token only, since
# robotparser does case-insensitive prefix matching internally).
_OUR_AGENT = "bikegrid-scraper"


# HTTP statuses worth retrying: rate-limit + transient server errors.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class CloudflareChallenge(Exception):
    """Raised when a response is a Cloudflare bot challenge (``cf-mitigated``).

    These come back as 429/403 with a JavaScript "Verifying your connection…"
    interstitial that an httpx client can't solve. Retrying is pointless and
    actively harmful: every extra request further degrades our IP reputation,
    making Cloudflare challenge *more* of our vendors. So we fail fast and let
    the caller treat the whole vendor as failed (without wiping its data).
    """

    def __init__(self, url: str, response: httpx.Response):
        self.url = url
        self.response = response
        mitigation = response.headers.get("cf-mitigated", "challenge")
        super().__init__(
            f"Cloudflare bot challenge ({mitigation}, HTTP {response.status_code}) for {url} — "
            "cannot be solved by the scraper; needs a challenge-solving egress (residential "
            "proxy or scraping API)"
        )


def _is_cloudflare_challenge(resp: httpx.Response) -> bool:
    """True if the response is a Cloudflare managed/JS challenge, not real data.

    Cloudflare sets the ``cf-mitigated`` response header (value ``challenge`` for
    a managed challenge) when it interdicts a request. This is the documented,
    body-free signal, so we don't need to read/parse the HTML interstitial.
    """
    return bool(resp.headers.get("cf-mitigated"))


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict | None = None,
    retries: int = 3,
    base_delay: float = 1.0,
) -> httpx.Response:
    """GET with exponential backoff on transient failures (5xx/429/network).

    A single transient blip from a vendor shouldn't drop their whole dataset for
    the day. Non-retryable responses (e.g. 404) are returned as-is so the caller
    can decide; the last exception is re-raised if every attempt fails.

    A Cloudflare bot challenge is the exception: it is *not* transient, so we
    raise :class:`CloudflareChallenge` immediately rather than burning retries.
    """
    request_url, request_headers = _apply_proxy(url, headers)
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = await client.get(request_url, headers=request_headers, follow_redirects=True)
            if _is_cloudflare_challenge(resp):
                raise CloudflareChallenge(url, resp)
            if resp.status_code in _RETRYABLE_STATUS:
                raise httpx.HTTPStatusError(
                    f"retryable status {resp.status_code}", request=resp.request, response=resp
                )
            return resp
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "GET %s failed (attempt %d/%d): %s; retrying in %.1fs",
                    url, attempt + 1, retries, exc, delay,
                )
                await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


async def check_robots(base_url: str, client: httpx.AsyncClient) -> bool:
    """Return True if we're allowed to scrape this host.

    Uses stdlib urllib.robotparser, which correctly handles multiple
    user-agent blocks, comments, and longest-match-wins semantics — things
    the previous hand-rolled regex got wrong.
    """
    try:
        # Short timeout: a slow/unresponsive host shouldn't cost the full 30s
        # client timeout just to check robots.txt.
        request_url, request_headers = _apply_proxy(urljoin(base_url, "/robots.txt"), None)
        resp = await client.get(
            request_url, headers=request_headers, follow_redirects=True, timeout=5.0
        )
        # Missing/unavailable robots.txt is treated as permissive (RFC 9309).
        if resp.status_code != 200:
            return True
        rp = robotparser.RobotFileParser()
        rp.parse(resp.text.splitlines())
        for path in _PATHS_TO_CHECK:
            url = urljoin(base_url, path)
            if not rp.can_fetch(_OUR_AGENT, url):
                logger.warning("[%s] robots.txt disallows %s for %s", base_url, path, _OUR_AGENT)
                return False
        return True
    except Exception as exc:
        logger.warning("[%s] robots.txt check failed (%s); proceeding", base_url, exc)
        return True


def _looks_like_size(segment: str) -> bool:
    if re.match(r"^(One\s*Size|N/?A)$", segment, re.IGNORECASE):
        return True
    words = segment.split()
    return bool(words) and all(
        _SIZE_WORD_RE.match(w) or _SIZE_MEAS_RE.match(w) for w in words
    )


def extract_frame_size(raw: str) -> str:
    """Return just the size token from a variant title that may contain colour info.

    Splits on '/' and returns the first segment whose every word is a size word
    or a measurement (e.g. 'Small 27.5"', '39" small', 'L', '54cm').
    Falls back to the original string if no segment qualifies.
    """
    for part in [p.strip() for p in raw.split("/")]:
        if _looks_like_size(part):
            return part
    return raw


def parse_price(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(value).strip())
    try:
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def resolve_category(candidates: list[str], category_map: dict[str, str]) -> str | None:
    """Pick a normalised category from candidate strings.

    Two passes:
      1. Exact match — any candidate that is a literal key in category_map.
      2. Substring match — any candidate that *contains* a key. Keys are
         tried longest-first so "mountain bikes" beats "bikes" regardless
         of the order they were declared in the YAML config.
    """
    for candidate in candidates:
        if candidate in category_map:
            return category_map[candidate]
    sorted_keys = sorted(category_map.keys(), key=len, reverse=True)
    for candidate in candidates:
        for key in sorted_keys:
            if key in candidate:
                return category_map[key]
    return None
