import logging
import re
from urllib import robotparser
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)


# Paths we might fetch from any vendor. If robots.txt disallows any of them
# for our user agent, we skip the whole vendor.
_PATHS_TO_CHECK = ("/", "/products.json", "/products")

# Match the User-Agent header we send (case-insensitive token only, since
# robotparser does case-insensitive prefix matching internally).
_OUR_AGENT = "bikegrid-scraper"


async def check_robots(base_url: str, client: httpx.AsyncClient) -> bool:
    """Return True if we're allowed to scrape this host.

    Uses stdlib urllib.robotparser, which correctly handles multiple
    user-agent blocks, comments, and longest-match-wins semantics — things
    the previous hand-rolled regex got wrong.
    """
    try:
        resp = await client.get(urljoin(base_url, "/robots.txt"), follow_redirects=True)
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
