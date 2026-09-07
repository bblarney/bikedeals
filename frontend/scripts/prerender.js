// Build-time prerender. Runs after `vite build` (client) and `vite build --ssr`
// (server bundle), and rewrites dist/ so every listed route ships real HTML
// instead of an empty <div id="root">.
//
// Data-bearing where it can be, offline where it must be. When
// VITE_API_BASE_URL is set (it is, in the Pages build) the routes that show
// numbers or cards have their API responses fetched first and handed to the
// render as a seed, so a shop page ships its stats and a feed ships its first
// page of bikes. Every fetch fails open: a timeout, a non-200 or a dead API
// drops that one seed with a warning, and the route renders its empty-data
// shape exactly as it did before. Nothing here can fail the build; that
// guarantee predates the seeding and it still holds.
//
// The client still uses createRoot, not hydrateRoot: the prerendered markup is
// for crawlers and first paint, and React discards and re-renders it on mount.
// The seed is therefore also written into the page as JSON, and main.jsx loads
// it into the browser's cache before that first client render, so the numbers
// stay on screen rather than flashing to a placeholder while they refetch.

import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = join(root, 'dist')

// Guide routes are derived, not listed, so adding a guide to content/guides.js
// prerenders it automatically. Forgetting this list is otherwise a hard 404 in
// production: public/_redirects has no catch-all. That import is also why
// content/guides.js must stay free of JSX and import.meta.env: it is loaded
// here by bare node, outside Vite.
const { GUIDE_PATHS } = await import(
  pathToFileURL(join(root, 'src', 'content', 'guides.js')).href
)

// Same deal: bare node, so src/content/categories.js stays plain JS. Every
// category is a route, and an unlisted route is a hard 404 in production.
const { CATEGORY_PATHS } = await import(
  pathToFileURL(join(root, 'src', 'content', 'categories.js')).href
)

// Every shop page. Generated from the vendor registry by scripts/gen_shops.py,
// so adding a vendor and regenerating is what makes its page exist; there is no
// hand-maintained list to forget. ~108 routes, each a small static file.
const { SHOP_PATHS } = await import(
  pathToFileURL(join(root, 'src', 'content', 'shops.js')).href
)

const ROUTES = [
  '/',
  '/deals',
  ...CATEGORY_PATHS,
  '/trends',
  '/shops',
  ...SHOP_PATHS,
  '/about',
  '/contact',
  '/data',
  '/sitemap',
  '/terms',
  '/privacy',
  ...GUIDE_PATHS,
]

// Mirrors seo.js so a prerendered canonical matches the client-rendered one.
const SITE = (process.env.VITE_PUBLIC_URL || 'https://bikegrid.com.au').replace(/\/$/, '')

// Where the seed comes from. Unset means a local build, which stays offline.
// Same variable the client bundle reads, so the build fetches from the API the
// page will talk to.
const API = (process.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const FETCH_TIMEOUT_MS = 15_000

// The API rate-limits each route at 120 requests a minute per IP (see
// docs/api-design.md), and this build asks /api/v1/bikes and /meta/filters for
// every shop page: ~115 each today, and one more per vendor added. Pace each
// route under that ceiling rather than burst and let the last shops 429 into
// their empty shape. Routes run in parallel, so the whole prefetch takes about
// as long as the busiest route: ~70 s at today's vendor count.
const PER_ROUTE_PER_MINUTE = 100
const SPACING_MS = Math.ceil(60_000 / PER_ROUTE_PER_MINUTE)

// pathToFileURL, not the bare path: Node's ESM loader rejects Windows absolute
// paths ("c:" is not a supported URL scheme).
const { render, prerenderQueries, queryString } = await import(
  pathToFileURL(join(root, 'dist-ssr', 'entry-server.js')).href
)
const template = await readFile(join(dist, 'index.html'), 'utf8')

// React only hoists <title>/<meta>/<link> into <head> when it renders the whole
// document. We render a fragment, so the tags the page components declare come
// back inline in the body string; pull them out and merge them into the head
// ourselves. Keeps the metadata defined in one place (the page components).
const META_TAGS =
  /<title>[\s\S]*?<\/title>|<meta\s[^>]*\/?>|<link\s[^>]*rel="canonical"[^>]*\/?>/gi

function splitMeta(html) {
  const tags = html.match(META_TAGS) ?? []
  return { body: html.replace(META_TAGS, ''), tags }
}

function attr(tag, name) {
  return tag.match(new RegExp(`${name}="([^"]*)"`, 'i'))?.[1]
}

// data-prerendered so the client can drop this tag on mount. React appends its
// own canonical rather than deduping against static markup it did not create,
// so leaving this one in place gives every client-side navigation two competing
// canonicals, and Google ignores a page that declares two. See main.jsx.
function setCanonical(head, href) {
  return head
    .replace(/\s*<link[^>]*rel="canonical"[^>]*\/?>/gi, '')
    .replace(/(<meta property="og:url" content=")[^"]*(")/i, `$1${href}$2`)
    .replace(
      '</head>',
      `  <link rel="canonical" href="${href}" data-prerendered />\n  </head>`,
    )
}

function applyMeta(head, tags, route) {
  let out = head
  let sawCanonical = false
  for (const tag of tags) {
    if (/^<title>/i.test(tag)) {
      const title = tag.replace(/^<title>|<\/title>$/gi, '')
      out = out
        .replace(/<title>[\s\S]*?<\/title>/i, `<title>${title}</title>`)
        .replace(
          /(<meta property="og:title" content=")[^"]*(")/i,
          `$1${title}$2`,
        )
        .replace(
          /(<meta name="twitter:title" content=")[^"]*(")/i,
          `$1${title}$2`,
        )
      continue
    }
    if (attr(tag, 'name') === 'description') {
      const desc = attr(tag, 'content') ?? ''
      out = out
        .replace(
          /(<meta name="description" content=")[^"]*(")/i,
          `$1${desc}$2`,
        )
        .replace(
          /(<meta property="og:description" content=")[^"]*(")/i,
          `$1${desc}$2`,
        )
        .replace(
          /(<meta name="twitter:description" content=")[^"]*(")/i,
          `$1${desc}$2`,
        )
      continue
    }
    if (/rel="canonical"/i.test(tag)) {
      out = setCanonical(out, attr(tag, 'href') ?? '')
      sawCanonical = true
    }
  }
  // A route that declares no canonical of its own still gets one, rather than
  // shipping uncanonicalised.
  return sawCanonical ? out : setCanonical(out, SITE + route)
}

function outputPath(route) {
  return route === '/'
    ? join(dist, 'index.html')
    : join(dist, route.slice(1), 'index.html')
}

// --- the seed -------------------------------------------------------------

// One fetch per distinct URL, however many routes want it: /vendors feeds
// /shops and all ~108 shop pages, and the home and feed pages share /stats
// and /market. Failures are cached too, so a dead endpoint is tried once.
const responses = new Map()

async function fetchJson(url) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) })
    if (!res.ok) {
      console.warn(`  warning    ${url} answered ${res.status}; route keeps its empty shape`)
      return null
    }
    return await res.json()
  } catch (err) {
    console.warn(`  warning    ${url} failed (${err.name}); route keeps its empty shape`)
    return null
  }
}

function urlFor(query) {
  return API + query.path + queryString(query.params)
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// Fetch every distinct URL up front, grouped by API route: each route's URLs
// go one at a time with SPACING_MS between them, and the routes run alongside
// each other.
async function prefetchAll() {
  const byRoute = new Map()
  for (const route of ROUTES) {
    for (const query of prerenderQueries(route)) {
      const url = urlFor(query)
      if (!byRoute.has(query.path)) byRoute.set(query.path, new Set())
      byRoute.get(query.path).add(url)
    }
  }
  const total = [...byRoute.values()].reduce((n, urls) => n + urls.size, 0)
  const busiest = Math.max(...[...byRoute.values()].map((urls) => urls.size))
  console.log(
    `  fetching   ${total} API responses from ${API} ` +
      `(${byRoute.size} routes, paced at ${PER_ROUTE_PER_MINUTE}/min; about ${Math.ceil((busiest * SPACING_MS) / 1000)} s)`,
  )
  await Promise.all(
    [...byRoute.values()].map(async (urls) => {
      let first = true
      for (const url of urls) {
        if (!first) await sleep(SPACING_MS)
        first = false
        responses.set(url, await fetchJson(url))
      }
    }),
  )
  const ok = [...responses.values()].filter((v) => v != null).length
  console.log(`  fetched    ${ok}/${total} API responses\n`)
}

function seedFor(route) {
  if (!API) return []
  return prerenderQueries(route).flatMap((query) => {
    const data = responses.get(urlFor(query))
    return data == null ? [] : [{ queryKey: query.queryKey, data }]
  })
}

// The seed, inlined for main.jsx. `<` is escaped so a shop's product title
// containing "</script>" cannot end the block early: this is third-party text
// from a hundred shops, and it is going inside a <script>.
const BUILT_AT = new Date().toISOString()

function stateScript(seed) {
  if (seed.length === 0) return ''
  const json = JSON.stringify({ at: BUILT_AT, queries: seed }).replace(/</g, '\\u003c')
  return `<script id="prerender-state" type="application/json">${json}</script>`
}

// --- the render -----------------------------------------------------------

// The client routes that are NOT prerendered (/bikes/:id, /unsubscribe) are
// rewritten to this file by _redirects, not to index.html. index.html is the
// prerendered home page, and serving that for a bike detail page would give
// every one of them a canonical pointing at the homepage in its pre-JS HTML,
// which invites Google to drop them. app-shell.html is the original empty shell:
// no body content, no canonical, so the client is free to supply both.
await writeFile(join(dist, 'app-shell.html'), template, 'utf8')
console.log('  wrote      app-shell.html (fallback for /bikes/*, /unsubscribe)')

if (API) await prefetchAll()
else console.log('  offline    VITE_API_BASE_URL is unset; prerendering without data\n')

for (const route of ROUTES) {
  // Let a throw fail the build. Silently shipping the empty shell for a route
  // is the exact failure this script exists to prevent.
  const seed = seedFor(route)
  const { body, tags } = splitMeta(render(route, seed))

  const [head, tail] = template.split('<body>')
  const html =
    applyMeta(head, tags, route) +
    '<body>' +
    tail.replace('<div id="root"></div>', `<div id="root">${body}</div>${stateScript(seed)}`)

  const file = outputPath(route)
  await mkdir(dirname(file), { recursive: true })
  await writeFile(file, html, 'utf8')

  const kb = (Buffer.byteLength(html) / 1024).toFixed(1)
  const seeded = seed.length ? ` (${seed.length} queries seeded)` : ''
  console.log(`  prerendered ${route.padEnd(34)} -> ${kb} kB${seeded}`)
}

console.log(`\nPrerendered ${ROUTES.length} routes.`)
