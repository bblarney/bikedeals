/**
 * BikeGrid scraper egress proxy (Cloudflare Worker).
 *
 * Why this exists: the daily scrape runs on GitHub Actions, whose datacenter IP
 * range Cloudflare/Shopify block as a class (every runner IP gets the same 429 /
 * 403 challenge). This Worker re-issues each vendor request from Cloudflare's own
 * network, whose egress IPs have good reputation, recovering the Shopify feeds.
 *
 * Contract with the scraper (see scrapers/utils.py::_apply_proxy):
 *   - Target URL arrives in the `X-Target-URL` request header.
 *   - Shared secret arrives in the `X-Proxy-Token` header, checked against the
 *     `PROXY_TOKEN` Worker secret. Missing/wrong -> 403 (not an open proxy).
 *   - All other request headers (notably the polite User-Agent) are forwarded
 *     to the origin unchanged.
 *
 * The origin response is passed back faithfully: same status code, and the
 * `cf-mitigated`, `Link`, and `Content-Type` headers preserved — the scraper
 * relies on all three (Cloudflare-challenge detection, Shopify pagination, JSON
 * parsing). The body is buffered and returned decompressed.
 */

// Vendor hostnames allowed as proxy targets — defense-in-depth so a leaked
// token can't turn this into a general-purpose open proxy. Stored with any
// leading "www." stripped; the incoming host is normalised the same way, so a
// single entry covers both the apex and www variants.
//
// Regenerate when the vendor list changes (from the repo root). The `_`-prefixed
// template files are skipped — they carry a placeholder host, not a real vendor:
//   grep -h -i base_url scrapers/vendors/[!_]*.yaml \
//     | sed -E 's/.*base_url:\s*//; s/["'"'"']//g; s#https?://(www\.)?##; s#/.*##' \
//     | sort -u
const ALLOWED_HOSTS = new Set([
  "99bikes.com.au",
  "abcbikes.com.au",
  "alchemycycletrader.com.au",
  "ampdbros.com.au",
  "baybikeco.com.au",
  "baysidecycles.com.au",
  "bicycle-centre.com.au",
  "bicyclecentrebelmont.com.au",
  "bicycleexpress.com.au",
  "bicyclefix.com.au",
  "bicyclesuperstore.com.au",
  "bicycleworkshop.com.au",
  "bikecentralgc.com.au",
  "bikeforcejoondalup.com.au",
  "bikeline.com.au",
  "bikenow.com.au",
  "bikeology.com.au",
  "bikes.com.au",
  "bikesonline.com.au",
  "bikezonefitzroy.com.au",
  "canberracyclery.com.au",
  "canyon.com",
  "ccache.cc",
  "crooze.com.au",
  "currumbincycles.com.au",
  "curvecycling.com",
  "cyclespot.com.au",
  "cycleworld.com.au",
  "cyclezone.com.au",
  "degrandi.com.au",
  "driftbikes.com.au",
  "ebikessuperstore.com.au",
  "electricbikesbrisbane.com.au",
  "empirecycles.com.au",
  "fitzroycycles.com.au",
  "giantbairnsdale.com.au",
  "giantballarat.com.au",
  "giantbendigo.com.au",
  "giantbrisbane.com.au",
  "giantbundaberg.com.au",
  "giantcastlemaine.com.au",
  "giantdevonport.com.au",
  "giantechuca.com.au",
  "giantgoldcoast.com.au",
  "giantlygonst.com.au",
  "giantmandurah.com.au",
  "giantmudgee.com.au",
  "giantosbornepark.com.au",
  "giantramsgate.com.au",
  "giantrockhampton.com.au",
  "giantsthelens.com",
  "giantsthyarra.com.au",
  "giantsunshinecoast.com.au",
  "giantsydney.com.au",
  "gianttamworth.com.au",
  "gianttuggerah.com.au",
  "giantwollongong.com.au",
  "glowwormbicycles.com.au",
  "happywheels.com.au",
  "hendrys.com.au",
  "ivanhoecycles.com.au",
  "jetcycles.com.au",
  "justridenerang.com.au",
  "lekkerbikes.com.au",
  "lifecyclebikes.com.au",
  "livelifecycling.com.au",
  "macarthurebikes.com.au",
  "mackaycycles.com.au",
  "mcbaincycles.com.au",
  "melbournebicycles.com.au",
  "myride.com.au",
  "offcourse.bike",
  "omafiets.com.au",
  "pedalheads.com.au",
  "pedalinn.au",
  "pedl.com.au",
  "planetcycles.com.au",
  "progearbikes.com.au",
  "reidcycles.com.au",
  "ride.net.au",
  "ridenroll.com.au",
  "rideunionbikeco.com.au",
  "saintcloud.com.au",
  "summitcycles.bike",
  "supremecycles.com.au",
  "thebicyclecompany.com.au",
  "thebikeshop.au",
  "themountainbiker.com.au",
  "treadlybikeshop.com.au",
  "velectrix.com.au",
  "velofix.com.au",
  "venturecycles.com.au",
  "westcoastcycles.com.au",
  "wheelhaus.com.au",
  "wollongongbikehub.com.au",
  "woolyswheels.com.au",
]);

// Request headers we must not forward to the origin: our own control headers
// and hop-by-hop / connection-specific headers.
const STRIP_REQUEST_HEADERS = new Set([
  "x-target-url",
  "x-proxy-token",
  "host",
  "connection",
  "accept-encoding", // let the Worker's fetch negotiate + decompress
]);

// Response headers we must not copy back: they describe a transfer encoding the
// buffered body no longer has.
const STRIP_RESPONSE_HEADERS = new Set([
  "content-encoding",
  "content-length",
  "transfer-encoding",
  "connection",
]);

function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function normaliseHost(hostname) {
  return hostname.replace(/^www\./, "").toLowerCase();
}

export default {
  async fetch(request, env) {
    if (!env.PROXY_TOKEN) {
      return json(500, { error: "PROXY_TOKEN secret not configured on the Worker" });
    }
    if (request.headers.get("X-Proxy-Token") !== env.PROXY_TOKEN) {
      return json(403, { error: "invalid or missing X-Proxy-Token" });
    }

    const target = request.headers.get("X-Target-URL");
    if (!target) {
      return json(400, { error: "missing X-Target-URL header" });
    }

    let url;
    try {
      url = new URL(target);
    } catch {
      return json(400, { error: `X-Target-URL is not a valid URL: ${target}` });
    }
    if (url.protocol !== "https:") {
      return json(400, { error: "only https targets are allowed" });
    }
    if (!ALLOWED_HOSTS.has(normaliseHost(url.hostname))) {
      // Distinct from a real vendor block (429 / cf-mitigated), so a forgotten
      // allowlist update is easy to spot in the scrape logs.
      return json(403, { error: `host not in allowlist: ${url.hostname}` });
    }

    const fwdHeaders = new Headers();
    for (const [name, value] of request.headers) {
      if (!STRIP_REQUEST_HEADERS.has(name.toLowerCase())) {
        fwdHeaders.set(name, value);
      }
    }

    let originResp;
    try {
      originResp = await fetch(url.toString(), {
        method: "GET",
        headers: fwdHeaders,
        redirect: "follow", // resolve redirects here; the caller never sees a 3xx
      });
    } catch (err) {
      // Network-level failure: 502 is retryable on the scraper side.
      return json(502, { error: `upstream fetch failed: ${err}` });
    }

    // Buffer the (already-decompressed) body and echo the origin status +
    // meaningful headers back to the caller.
    const body = await originResp.arrayBuffer();
    const respHeaders = new Headers();
    for (const [name, value] of originResp.headers) {
      if (!STRIP_RESPONSE_HEADERS.has(name.toLowerCase())) {
        respHeaders.set(name, value);
      }
    }
    return new Response(body, { status: originResp.status, headers: respHeaders });
  },
};
