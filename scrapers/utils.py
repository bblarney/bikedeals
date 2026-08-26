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


# Shop copy spells the top Shimano tier "Dura-Ace", "Dura Ace" and "DuraAce",
# and _GROUPSET_RE accepts all three. The per-word casing below splits on
# whitespace, so only the hyphenated form ever reaches the "dura-ace" entry --
# left alone, one groupset arrives in the facet as three separate values and
# splits the top rung of any Shimano-vs-SRAM comparison. Collapse to the
# hyphenated spelling before the words are split.
_DURA_ACE_RE = re.compile(r"\bdura[\s\-]?ace\b", re.IGNORECASE)


def _normalise_groupset(raw: str) -> str:
    raw = _DURA_ACE_RE.sub("Dura-Ace", raw)
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
    # Three- and two-letter abbreviations used by MTB brands (Santa Cruz, Yeti,
    # Mondraker, Juliana). Without these, variant titles like
    # "Matte Deep Purple / SML" have no segment that looks like a size, so the
    # colour leaks into frame_size and pollutes the size filter.
    r"|SML|MED|LGE|XLG|SM|MD|LG|ML"
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


# Stand-in for the proxy endpoint in any text that might be shown or shared.
PROXY_PLACEHOLDER = "<scraper-proxy>"


def redact_proxy(text: str) -> str:
    """Strip the proxy endpoint out of user-visible text.

    The proxy URL is not a credential (the token is), but it is the one piece of
    private infrastructure in an otherwise public project, and it reaches humans
    through several channels: the daily summary email, ``scrape_summary.json``,
    and CI logs — any of which can end up pasted into a public issue or PR.
    Naming it there also buys nothing diagnostically: when a proxied request
    fails, the useful URL is the *vendor's*, not ours.

    A no-op when no proxy is configured.
    """
    if not SCRAPER_PROXY_URL:
        return text
    return text.replace(SCRAPER_PROXY_URL, PROXY_PLACEHOLDER)


def _restore_target_url(resp: httpx.Response, target_url: str) -> None:
    """Point a proxied response's ``request`` back at the vendor URL.

    Every pipeline calls ``resp.raise_for_status()``, and httpx builds that
    message from ``resp.request.url`` — which, for a proxied request, is the
    Worker. That produced errors like "403 Forbidden for url
    '<scraper-proxy>'": it leaked the endpoint *and* named the wrong host, which
    is precisely why a vendor missing from the Worker's allowlist read as a
    mysterious proxy fault instead of a config omission.

    Rewriting the request here fixes both at a single point, so no pipeline has
    to know the proxy exists.

    The proxy control headers are dropped rather than copied across: the
    rewritten request is attached to any raised ``HTTPStatusError``, and
    ``X-Proxy-Token`` is a real credential that should not ride along on an
    exception object that gets logged with ``exc_info``.
    """
    if not SCRAPER_PROXY_URL:
        return
    try:
        original = resp.request
    except RuntimeError:
        # httpx raises if no request was ever attached to the response.
        original = None
    headers = (
        {
            k: v
            for k, v in original.headers.items()
            if k.lower() not in ("x-target-url", "x-proxy-token")
        }
        if original is not None
        else {}
    )
    resp.request = httpx.Request("GET", target_url, headers=headers)


# Match the User-Agent header we send (case-insensitive token only, since
# robotparser does case-insensitive prefix matching internally).
_OUR_AGENT = "bikegrid-scraper"


# HTTP statuses worth retrying: rate-limit + transient server errors.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class CloudflareChallenge(Exception):
    """Raised when a response is Cloudflare interdicting us, not vendor data.

    Two shapes of the same problem: a *challenge* (429/403 with a JavaScript
    "Verifying your connection…" interstitial that an httpx client can't solve)
    and a *block* (a WAF rule or ban that returns the "Attention Required" page
    outright). Neither is transient, and retrying is actively harmful: every
    extra request further degrades our IP reputation, making Cloudflare
    challenge *more* of our vendors. So we fail fast and let the caller treat
    the whole vendor as failed (without wiping its data).
    """

    def __init__(self, url: str, response: httpx.Response, mitigation: str | None = None):
        self.url = url
        self.response = response
        mitigation = mitigation or response.headers.get("cf-mitigated", "challenge")
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


# Text unique to Cloudflare's own block page. Checked against the body because
# a *block* — unlike a challenge — sets no `cf-mitigated` header.
_CF_BLOCK_MARKERS = (
    "Attention Required! | Cloudflare",
    "Sorry, you have been blocked",
    "cf-error-details",
)


def _is_cloudflare_block(resp: httpx.Response) -> bool:
    """True if a 403/429 is Cloudflare blocking us rather than the shop's origin.

    A WAF rule (or the ban that follows repeated hits) returns a plain 403 with
    Cloudflare's "Attention Required" page and no ``cf-mitigated`` header, so it
    is indistinguishable from an ordinary forbidden response until the body is
    read. That cost a real diagnosis: a shop whose zone blocks our datacenter
    egress on *every* path — including robots.txt — was reported for weeks as
    "0 bikes scraped", which reads like a broken selector rather than an egress
    problem no config change can fix.
    """
    if resp.status_code not in (403, 429):
        return False
    if "html" not in resp.headers.get("content-type", "").lower():
        return False
    try:
        body = resp.text
    except Exception:  # undecodable body — not a block page we can identify
        return False
    return any(marker in body for marker in _CF_BLOCK_MARKERS)


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
            # Re-point the response at the vendor before anything can read
            # resp.request: callers raise_for_status() off it, and it must name
            # the shop, not our proxy. See _restore_target_url.
            _restore_target_url(resp, url)
            if _is_cloudflare_challenge(resp):
                raise CloudflareChallenge(url, resp)
            if _is_cloudflare_block(resp):
                raise CloudflareChallenge(url, resp, mitigation="block")
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
                    url, attempt + 1, retries, redact_proxy(str(exc)), delay,
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
        logger.warning(
            "[%s] robots.txt check failed (%s); proceeding", base_url, redact_proxy(str(exc))
        )
        return True


def _looks_like_size(segment: str) -> bool:
    if re.match(r"^(One\s*Size|N/?A)$", segment, re.IGNORECASE):
        return True
    words = segment.split()
    return bool(words) and all(
        _SIZE_WORD_RE.match(w) or _SIZE_MEAS_RE.match(w) for w in words
    )


# --- canonical frame sizes ---------------------------------------------------
#
# `extract_frame_size` picks the size *segment* out of a variant title. It does
# not make two shops agree on what that segment says, and they do not: the live
# size facet had 536 distinct values, including thirty spellings of Large
# ("L", "Lg", "LGE", "LRG", "LARGE - 56", "Large 29\" Wheels",
# "L (Large 170cm - 185cm)"), colours that leaked through as a fallback
# ("Chrome Blue", "Light Blue"), tyre widths ("28mm"), top-tube measurements
# ("20.50 TT RSD"), and "Frameset only". Picking "M" from a dropdown could not
# return every medium, which for a bike shopper is the filter that matters most.
#
# The canonical value goes in `frame_size`; the shop's own wording is kept in
# `frame_size_raw` and is what `make_bike_id` hashes, so canonicalising cannot
# change a single bike's id — no broken detail URLs, no orphaned price history.
#
# Four families are emitted, and anything else canonicalises to None so it drops
# out of the facet instead of padding it:
#
#   alpha   XXXS..XXXL, plus the M/L-style intermediates some brands ship
#   cm      road sizing, "54cm"
#   inch    12"-24", how kids' bikes and inch-sized MTB frames are sold
#   None    unknown ("N/A", "One Size"), or not a size at all
#
# 26"/27.5"/29" alone are deliberately None: those are *wheel* diameters, not
# frame sizes, and treating them as sizes is what put "Large 29\"" and "29" in
# the same dropdown as two different options.

_ALPHA_SCALE = ("XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL")

# Ordered longest/most-specific first: "xx-large" must be tried before "large",
# or every XXL collapses to L. Same trick as _BRAND_SUFFIXES in scrapers.models.
_ALPHA_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?:3x|xxx)[\s-]*small|3xs|4xs", "XXXS"),
    (r"(?:2x|xx)[\s-]*small|xxs|2xs", "XXS"),
    (r"x[\s-]*small|extra[\s-]*small|\bxs\b", "XS"),
    (r"(?:3x|xxx)[\s-]*large|3xl|xxxl|4xl", "XXXL"),
    (r"(?:2x|xx)[\s-]*large|xxl|2xl", "XXL"),
    (r"x[\s-]*large|extra[\s-]*large|\bxl\b|\bxlg\b", "XL"),
    # Intermediate sizes are real (Specialized ships S/M and M/L), so they are
    # kept rather than rounded into a neighbour.
    #
    # S/M demands an explicit separator, M/L does not, and the asymmetry is what
    # the data says. Bare "SM" appears 197 times in a 5,478-row sample, next to
    # "MD" (211) and "LG" (199) — it is the Small in Small/Medium/Large, not an
    # intermediate. There is no "MDLG", so a bare "ML" has nothing to abbreviate
    # and really is M/L.
    (r"\bs[\s/\\-]m\b|\bsmall[\s/\\-]medium\b", "S/M"),
    (r"\bm[\s/\\-]?l\b|\bmedium[\s/\\-]large\b", "M/L"),
    (r"\bsmall\b|\bsml\b|\bsm\b|\bs\b", "S"),
    (r"\bmedium\b|\bmed\b|\bmd\b|\bm\b", "M"),
    (r"\blarge\b|\blge\b|\blrg\b|\blg\b|\bl\b", "L"),
)
_ALPHA_RE = tuple((re.compile(p, re.IGNORECASE), canon) for p, canon in _ALPHA_PATTERNS)

# Specialized's S-Sizing, which replaced alpha sizes across their range and is
# ~5% of the live catalogue ("S2", "S3", "S4", "S5").
_S_SIZING = {
    "s1": "XS", "s2": "S", "s3": "M", "s4": "L", "s5": "XL", "s6": "XXL",
}
_S_SIZING_RE = re.compile(r"^\s*(s[1-6])\s*$", re.IGNORECASE)

# "M54", "L56" — an alpha size welded to its centimetre equivalent. No word
# boundary exists between the letter and the digits, so the alpha patterns above
# cannot see it.
_ALPHA_CM_RE = re.compile(r"^\s*(xxs|xs|s|m|l|xl|xxl)\s*[-]?\s*\d{2}(?:\.\d)?\s*$", re.IGNORECASE)

# Road sizing. The range is generous at both ends (a 38cm exists, so does a
# 68cm) but stops well short of the numbers that are really wheel diameters.
_CM_MIN, _CM_MAX = 38.0, 68.0
_CM_MARKED_RE = re.compile(r"\b(\d{2}(?:\.\d)?)\s*cm\b", re.IGNORECASE)
_CM_BARE_RE = re.compile(r"\b(\d{2}(?:\.\d)?)\b")
# Some shops quote millimetres: "560" is a 56cm frame.
_MM_RE = re.compile(r"\b([3-6]\d{2})\b")

# Inch sizing: kids' wheels (12-24) and the inch-numbered MTB frames (15-21).
# Integers only — "20.50 TT" is a top-tube measurement, not a 20.5" frame.
_INCH_SIZES = frozenset({12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 24})
_INCH_MARKED_RE = re.compile(r"\b(\d{2})\s*(?:\"|''|in\b|inch\b|inches\b)", re.IGNORECASE)
_INCH_BARE_RE = re.compile(r"^\s*(\d{2})\s*$")

# Values that say "we don't know", as opposed to naming a size.
_UNKNOWN_SIZES = frozenset({"n/a", "na", "one size", "onesize", "", "-"})

# Top-tube length, which one shop publishes instead of a frame size
# ("20.50 TT", "21.00 TT RHD"). It is a measurement in inches of a different
# part of the bike, and the digits look enough like a size to be dangerous:
# "18.50 TT" through "21.50 TT" all landed on 50cm and 65cm frames.
_TOP_TUBE_RE = re.compile(r"\bTT\b")


def canonical_frame_size(raw: str | None) -> str | None:
    """Map a shop's frame-size wording onto a shared scale, or None.

    None means "not a usable size" — unknown, or a colour/measurement that is
    not a size at all. Callers keep the original string; this only decides what
    the filter and the facet see.
    """
    if not raw:
        return None
    text = " ".join(str(raw).split())
    if text.lower() in _UNKNOWN_SIZES or _TOP_TUBE_RE.search(text):
        return None

    s_sized = _S_SIZING_RE.match(text)
    if s_sized:
        return _S_SIZING[s_sized.group(1).lower()]

    welded = _ALPHA_CM_RE.match(text)
    if welded:
        return welded.group(1).upper()

    # Alpha wins over a measurement in the same string: "51cm - Small" and
    # "54 (M)" are one size expressed twice, and the site's size filter is built
    # around the alpha scale. The exact centimetres survive in frame_size_raw.
    for pattern, canon in _ALPHA_RE:
        if pattern.search(text):
            return canon

    marked_cm = _CM_MARKED_RE.search(text)
    if marked_cm and _CM_MIN <= float(marked_cm.group(1)) <= _CM_MAX:
        return _format_cm(marked_cm.group(1))

    marked_inch = _INCH_MARKED_RE.search(text)
    if marked_inch and int(marked_inch.group(1)) in _INCH_SIZES:
        return f'{int(marked_inch.group(1))}"'

    bare_inch = _INCH_BARE_RE.match(text)
    if bare_inch and int(bare_inch.group(1)) in _INCH_SIZES:
        return f'{int(bare_inch.group(1))}"'

    for candidate in _CM_BARE_RE.findall(text):
        if _CM_MIN <= float(candidate) <= _CM_MAX:
            return _format_cm(candidate)

    millimetres = _MM_RE.search(text)
    if millimetres and _CM_MIN <= int(millimetres.group(1)) / 10 <= _CM_MAX:
        return _format_cm(f"{int(millimetres.group(1)) / 10:g}")

    return None


def _format_cm(value: str) -> str:
    number = float(value)
    return f"{number:g}cm"


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
