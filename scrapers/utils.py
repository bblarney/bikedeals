import logging
import re

import httpx

logger = logging.getLogger(__name__)


async def check_robots(base_url: str, client: httpx.AsyncClient) -> bool:
    try:
        resp = await client.get(f"{base_url}/robots.txt", follow_redirects=True)
        if resp.status_code != 200:
            return True
        text = resp.text.lower()
        in_relevant_agent = False
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                in_relevant_agent = agent in ("*", "bikedeals-scraper")
            elif in_relevant_agent and line.startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path in ("/", "/*", "/products.json", "/products"):
                    logger.warning("[%s] robots.txt disallows scraping: %s", base_url, path)
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
    """Two-pass lookup: exact key match first, then substring match."""
    for candidate in candidates:
        if candidate in category_map:
            return category_map[candidate]
    for candidate in candidates:
        for key, value in category_map.items():
            if key in candidate:
                return value
    return None
