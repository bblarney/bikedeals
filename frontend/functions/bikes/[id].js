// Server-render the <head> of /bikes/:id at the edge.
//
// WHY THIS EXISTS
// ---------------
// /bikes/* is rewritten to app-shell.html — a bare <div id="root"></div>. The
// API's sitemap.xml advertises one URL per in-stock bike (38k+ of them), so the
// highest-volume, longest-tail pages on the site were all served to crawlers as
// the same empty document: no title, no description, no canonical, and no
// Product JSON-LD. Google renders JavaScript eventually, but render budget is
// the binding constraint on a young domain with tens of thousands of URLs, and
// merchant/rich results are driven by that JSON-LD specifically.
//
// A Pages Function runs BEFORE the static-asset and _redirects lookup, so this
// intercepts /bikes/:id, fetches the bike, and returns the same shell with a
// populated head. The client-side app is untouched: it still mounts, fetches,
// and renders exactly as before.
//
// THREE THINGS ARE LOAD-BEARING
//
//  1. **It fails open.** Any error, timeout or non-200 from the API returns the
//     unmodified shell with a 200. A broken API must degrade to today's
//     behaviour, never to a blank or error page.
//
//  2. **404 means 404.** When the API says the bike is gone we return HTTP 404
//     with the shell. This is the real fix for what BikeDetailPage.jsx calls
//     "the highest-volume soft 404 on the site": a static host cannot answer 404
//     for a dynamic path, so the app had to render a client-side noindex and
//     hope Googlebot got there. It still does, as the fallback — but crawlers
//     now get the status code on the first byte. Note the asymmetry: only an
//     explicit 404 from the API produces a 404. An API outage must not
//     de-index the entire catalogue.
//
//  3. **Everything injected is escaped.** Titles and descriptions are scraped
//     third-party text from 97 shops. Attribute values go through escapeAttr and
//     the JSON-LD through serializeJsonLd (which neutralises `<`, so a product
//     title containing `</script>` cannot break out).
//
// The meta and JSON-LD come from ../../src/lib/bikeMeta.js — the same module the
// React page uses — so the pre-JS head and the client-rendered head cannot drift
// apart. That module must stay free of JSX and import.meta.env; this runtime has
// neither.

import {
  buildBikeMetaFor,
  buildBikeJsonLdFor,
  serializeJsonLd,
} from '../../src/lib/bikeMeta.js'

const DEFAULT_API = 'https://api.bikegrid.com.au'
const DEFAULT_SITE = 'https://bikegrid.com.au'

// Budget for the upstream call. The shell still renders if we blow it; a slow
// API should cost a crawler its metadata, not the page.
const API_TIMEOUT_MS = 2500

function escapeAttr(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// Every injection goes through a replacer FUNCTION, never a replacement string.
//
// In String.replace, `$1`..`$9`, `$&`, `` $` `` and `$'` are substitution
// patterns *in the replacement*. Bike descriptions contain prices — "$100" — so
// a string replacement silently expanded `$1` into capture group 1 and spliced
// the matched tag into its own content:
//
//   content="...Balance Bike for <meta name="description" content="00 at Reid…
//
// A function replacer is passed the match and returns the literal text, so no
// substitution happens. Do not "simplify" these back into template strings.
function replaceWith(html, re, value) {
  return html.replace(re, () => value)
}

// Replace the content of an existing tag, matched on the attribute that
// identifies it. app-shell.html already carries a full set of placeholder
// og:/twitter: tags (see frontend/index.html), so this rewrites rather than
// appends — appending would leave two of each.
function setMetaContent(html, attr, name, content) {
  const re = new RegExp(`<meta ${attr}="${name}" content="[^"]*"`, 'i')
  if (!re.test(html)) return html
  return replaceWith(html, re, `<meta ${attr}="${name}" content="${escapeAttr(content)}"`)
}

function renderHead(html, { meta, jsonLd }) {
  let out = html

  out = replaceWith(
    out,
    /<title>[\s\S]*?<\/title>/i,
    `<title>${escapeAttr(meta.title)}</title>`,
  )
  out = setMetaContent(out, 'name', 'description', meta.description)
  out = setMetaContent(out, 'property', 'og:title', meta.title)
  out = setMetaContent(out, 'property', 'og:description', meta.description)
  out = setMetaContent(out, 'property', 'og:url', meta.canonical)
  out = setMetaContent(out, 'name', 'twitter:title', meta.title)
  out = setMetaContent(out, 'name', 'twitter:description', meta.description)
  out = setMetaContent(out, 'property', 'og:type', 'product')

  // A share card showing the actual bike rather than the BikeGrid logo.
  if (jsonLd.image) {
    out = setMetaContent(out, 'property', 'og:image', jsonLd.image)
    out = setMetaContent(out, 'name', 'twitter:image', jsonLd.image)
    out = setMetaContent(out, 'property', 'og:image:alt', jsonLd.name)
  }

  // data-prerendered, matching scripts/prerender.js: main.jsx strips these on
  // mount. React appends its own canonical and JSON-LD rather than deduping
  // against markup it did not create, so leaving ours would give every page two
  // competing canonicals and two Product nodes after the first navigation.
  // Also a function replacer: the JSON-LD carries the same "$100" that broke the
  // meta tags, and `</head>` as a string pattern still expands `$` in the
  // replacement.
  out = replaceWith(
    out,
    '</head>',
    `  <link rel="canonical" href="${escapeAttr(meta.canonical)}" data-prerendered />\n` +
      `  <script type="application/ld+json" data-prerendered>${serializeJsonLd(jsonLd)}</script>\n` +
      '  </head>',
  )
  return out
}

function noindex(html) {
  return html.replace(
    '</head>',
    '  <meta name="robots" content="noindex" data-prerendered />\n  </head>',
  )
}

export async function onRequestGet(context) {
  const { request, params, env } = context
  const site = (env.SITE_URL || DEFAULT_SITE).replace(/\/$/, '')
  const apiBase = (env.API_BASE_URL || DEFAULT_API).replace(/\/$/, '')

  // The shell is a static asset of this same deployment.
  const shellUrl = new URL('/app-shell', request.url)
  const shellResponse = await env.ASSETS.fetch(new Request(shellUrl, { method: 'GET' }))
  const shell = await shellResponse.text()

  const html = (body, status) =>
    new Response(body, {
      status,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        // Mirrors the API's own bike cache (5 min), with a longer edge TTL:
        // listings only change after the nightly scrape.
        'Cache-Control': 'public, max-age=300, s-maxage=1800',
      },
    })

  const id = params.id
  // Defend the upstream call: ids are 16 hex chars (scrapers.models.make_bike_id).
  if (typeof id !== 'string' || !/^[a-zA-Z0-9_-]{1,64}$/.test(id)) {
    return html(noindex(shell), 404)
  }

  let bike
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS)
    let upstream
    try {
      upstream = await fetch(`${apiBase}/api/v1/bikes/${encodeURIComponent(id)}`, {
        signal: controller.signal,
        headers: { Accept: 'application/json' },
      })
    } finally {
      clearTimeout(timer)
    }

    if (upstream.status === 404) {
      // Gone for good: give the crawler the status, not a 200 with a thin page.
      return html(noindex(shell), 404)
    }
    if (!upstream.ok) return html(shell, 200) // fail open
    bike = await upstream.json()
  } catch {
    return html(shell, 200) // fail open: timeout, DNS, malformed JSON
  }

  try {
    const meta = buildBikeMetaFor(bike, site)
    const jsonLd = buildBikeJsonLdFor(bike, site)
    let out = renderHead(shell, { meta, jsonLd })
    // A listing that is no longer purchasable should not be indexed, even though
    // the page still renders its price history.
    if (bike.in_stock === false) out = noindex(out)
    return html(out, 200)
  } catch {
    return html(shell, 200)
  }
}
