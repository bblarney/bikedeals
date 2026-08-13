// Build-time prerender. Runs after `vite build` (client) and `vite build --ssr`
// (server bundle), and rewrites dist/ so every listed route ships real HTML
// instead of an empty <div id="root">.
//
// Deliberately offline: no route here fetches data, so the API can be cold or
// down during a build without affecting the output. See src/entry-server.jsx.
//
// The client still uses createRoot, not hydrateRoot — the prerendered markup is
// for crawlers and first paint, and React discards and re-renders it on mount.
// That keeps returning visitors (whose localStorage sends them to the deal feed
// rather than the landing page) free of hydration-mismatch errors. Those
// visitors are also never shown the discarded markup: see gateHead below.

import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = join(root, 'dist')

// Guide routes are derived, not listed, so adding a guide to content/guides.js
// prerenders it automatically. Forgetting this list is otherwise a hard 404 in
// production — public/_redirects has no catch-all. That import is also why
// content/guides.js must stay free of JSX and import.meta.env: it is loaded
// here by bare node, outside Vite.
const { GUIDE_PATHS } = await import(
  pathToFileURL(join(root, 'src', 'content', 'guides.js')).href
)

// Same deal: loaded by bare node, so src/lib/landing.js stays plain JS.
const { DEAL_FEED_GATE, DEAL_FEED_GATE_STYLE } = await import(
  pathToFileURL(join(root, 'src', 'lib', 'landing.js')).href
)

const ROUTES = [
  '/',
  '/about',
  '/contact',
  '/sitemap',
  '/terms',
  '/privacy',
  ...GUIDE_PATHS,
]

// Mirrors seo.js so a prerendered canonical matches the client-rendered one.
const SITE = (process.env.VITE_PUBLIC_URL || 'https://bikegrid.com.au').replace(/\/$/, '')

// pathToFileURL, not the bare path: Node's ESM loader rejects Windows absolute
// paths ("c:" is not a supported URL scheme).
const { render } = await import(
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
// canonicals — and Google ignores a page that declares two. See main.jsx.
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
  // The landing page declares no canonical of its own (MainLayout returns before
  // its meta block), so derive one rather than leaving the route uncanonicalised.
  return sawCanonical ? out : setCanonical(out, SITE + route)
}

// `/` is the one route whose prerendered markup is not what every visitor gets:
// it is the landing page, but a visitor with a stored region or a city-filtered
// URL renders the deal feed instead. Without this the landing page paints and
// is then thrown away on mount — a flash of the wrong page on every refresh.
// The gate hides it before first paint, for those visitors only; a crawler has
// no localStorage and no query string, so it still gets the landing page.
function gateHead(head) {
  return head.replace(
    '</head>',
    `  <script>${DEAL_FEED_GATE}</script>\n` +
      `  <style>${DEAL_FEED_GATE_STYLE}</style>\n  </head>`,
  )
}

// The id the gate's style hooks onto. Only ever present in prerendered markup —
// React renders its own tree into #root and never emits this wrapper.
function gateBody(body) {
  return `<div id="prerendered-landing">${body}</div>`
}

function outputPath(route) {
  return route === '/'
    ? join(dist, 'index.html')
    : join(dist, route.slice(1), 'index.html')
}

// The client routes that are NOT prerendered (/bikes/:id, /unsubscribe) are
// rewritten to this file by _redirects, not to index.html. index.html is now the
// prerendered landing page, and serving that for a bike detail page would give
// every one of them a canonical pointing at the homepage in its pre-JS HTML —
// which invites Google to drop them. app-shell.html is the original empty shell:
// no body content, no canonical, so the client is free to supply both.
await writeFile(join(dist, 'app-shell.html'), template, 'utf8')
console.log('  wrote      app-shell.html (fallback for /bikes/*, /unsubscribe)')

for (const route of ROUTES) {
  // Let a throw fail the build. Silently shipping the empty shell for a route
  // is the exact failure this script exists to prevent.
  const { body, tags } = splitMeta(render(route))

  const [head, tail] = template.split('<body>')
  const isLanding = route === '/'
  const rootHtml = isLanding ? gateBody(body) : body
  const headHtml = applyMeta(head, tags, route)
  const html =
    (isLanding ? gateHead(headHtml) : headHtml) +
    '<body>' +
    tail.replace('<div id="root"></div>', `<div id="root">${rootHtml}</div>`)

  const file = outputPath(route)
  await mkdir(dirname(file), { recursive: true })
  await writeFile(file, html, 'utf8')

  const kb = (Buffer.byteLength(html) / 1024).toFixed(1)
  console.log(`  prerendered ${route.padEnd(10)} -> ${kb} kB`)
}

console.log(`\nPrerendered ${ROUTES.length} routes.`)
