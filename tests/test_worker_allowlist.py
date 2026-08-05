"""The Cloudflare Worker's host allowlist must cover every registered vendor.

In CI the scrape egresses through `worker/worker.js`, which only proxies hosts in
its hardcoded `ALLOWED_HOSTS` set. Adding a vendor YAML without updating that set
lets the vendor pass every other check and then fail the nightly run with
`403 {"error": "host not in allowlist: ..."}` — which is what happened to the nine
shops added in cf62dd5. This test turns that silent, deploy-time drift into a
red build.

Note it can only catch a *stale file*; the deployed Worker is a separate artifact,
so a passing test still requires `npx wrangler deploy` (see worker/README.md).
"""
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

from scrapers.registry import load_registry

WORKER_JS = Path(__file__).resolve().parents[1] / "worker" / "worker.js"

_ALLOWED_HOSTS_BLOCK = re.compile(
    r"const ALLOWED_HOSTS = new Set\(\[(.*?)\]\);", re.DOTALL
)


def _normalise_host(hostname: str) -> str:
    """Mirror `normaliseHost` in worker.js: strip a leading "www." and lowercase."""
    return re.sub(r"^www\.", "", hostname.lower())


def _worker_allowed_hosts() -> set[str]:
    match = _ALLOWED_HOSTS_BLOCK.search(WORKER_JS.read_text(encoding="utf-8"))
    assert match, "could not find the ALLOWED_HOSTS set in worker.js"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _registry_hosts() -> set[str]:
    return {_normalise_host(urlparse(c.base_url).hostname or "") for c in load_registry()}


def test_worker_allowlist_covers_every_vendor():
    missing = _registry_hosts() - _worker_allowed_hosts()
    assert not missing, (
        "vendor hosts missing from ALLOWED_HOSTS in worker/worker.js: "
        f"{sorted(missing)}. Add them and redeploy the Worker (worker/README.md), "
        "or the nightly scrape 403s on these vendors."
    )


def test_worker_allowlist_has_no_stale_entries():
    """Removed vendors should leave the allowlist, keeping the proxy surface minimal."""
    stale = _worker_allowed_hosts() - _registry_hosts()
    assert not stale, (
        "ALLOWED_HOSTS in worker/worker.js lists hosts no longer in the vendor "
        f"registry: {sorted(stale)}"
    )


@pytest.mark.parametrize("host", ["example-bike-shop.com.au"])
def test_template_placeholder_hosts_are_not_allowlisted(host):
    """`_`-prefixed template YAMLs carry placeholder hosts that must never ship."""
    assert host not in _worker_allowed_hosts()
