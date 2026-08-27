# Frontend Design

Reflects `frontend/src/`. When the code and this document disagree, the code wins.

## Framework

**React 19 + Vite + Tailwind CSS 4**, with TanStack Query for server state and
filter values in URL query params. Routing is `react-router-dom`; the price-history
chart uses `recharts`. No global state store — none has been needed.

---

## Type

Two faces, defined as `@theme` tokens in `src/index.css` and loaded in
`index.html`.

- **Inter** sets everything: body, UI, labels, and every figure. Prices, counts
  and percentages carry `tabular-nums` so a column of them lines up, which is
  the job a monospace face was previously being carried for.
- **Archivo** (`font-display`) is for headings that announce a page: the home
  hero, the home section headings, the guide callout. Nothing else. It is a
  second voice, and a second voice competing with the data is what made the home
  page read as five fonts.

`src/lib/time.js` is the other half of that consistency. Freshness reads as
"today", "yesterday" or a date rather than "4h ago": the scrape runs once a day,
so an hour count was precision about nothing, and it changed every time the page
was opened without the data having changed. `formatShortDate` spells its months
out rather than calling `toLocaleDateString`, because Node's ICU renders en-AU
`month: 'short'` as "June" where a browser gives "Jun", and both render these
pages (see the prerender).

---

## Deployment

The frontend is a static build (`vite build` → `dist/`). Deploy to Cloudflare Pages or Vercel. Both are free and provide instant global CDN.

The API URL must be an environment variable:
```
VITE_API_BASE_URL=https://api.bikegrid.example.com
```

---

## Prerendering

`npm run build` is three steps: the client build, an SSR build of
`src/entry-server.jsx`, then `scripts/prerender.js`, which writes real HTML for
`/`, `/deals`, `/trends`, `/about`, `/contact`, `/data`, `/sitemap`, `/terms`,
`/privacy`, every category route listed in `src/content/categories.js`, and
every guide route listed in `src/content/guides.js`.

This exists because the SPA otherwise ships `<div id="root"></div>` and nothing
else. Crawlers that don't execute JavaScript — including the AdSense review
crawler — saw an empty document on every URL.

**The prerender never calls the API.** React Query only fetches from an effect,
which `renderToString` doesn't run, so pages render in their empty-data shape:
headings, copy, nav, footer. Dropdown options and deal data fill in on the
client. A build therefore succeeds while the API is cold or down.

Three things are load-bearing:

- **`createRoot`, not `hydrateRoot`.** React discards the prerendered markup and
  re-renders on mount. The markup is for crawlers and first paint only.
- **`app-shell.html`.** `/bikes/:id` and `/unsubscribe` are not prerendered and
  are rewritten to this bare shell, not to `index.html`. `index.html` is the
  prerendered home page; serving it for a bike detail page would give every one
  a canonical pointing at the homepage before JS runs.
- **`data-prerendered` on the canonical.** React appends its own canonical
  rather than replacing static markup it didn't create, so `main.jsx` removes
  the prerendered one on mount. Without that, every client-side navigation
  leaves two conflicting canonicals in the head.

Adding a client route means adding it to `ROUTES` in `scripts/prerender.js`, or
adding a fallback line to `public/_redirects` — the blanket `/* /index.html 200`
is gone, so an unlisted route 404s. That is deliberate: the old catch-all
answered every unknown URL with a 200 app shell, which Google reads as a soft
404.

Guide routes are the exception, and are handled structurally: `prerender.js`
imports `GUIDE_PATHS` from `src/content/guides.js` and concatenates it onto
`ROUTES`, so adding a guide to that array is enough. That import is why
`content/guides.js` must stay free of JSX, imports and `import.meta.env` — bare
`node` loads it, outside Vite. `src/content/categories.js` is imported the same
way and carries the same constraint.

Anything rendered during the prerender must tolerate the absence of `window`,
`document`, and `localStorage`. Effects and event handlers are safe; `useState`
initializers are not.

---

## Edge rendering `/bikes/:id`

`functions/bikes/[id].js` is a Cloudflare Pages Function that renders the `<head>`
of a bike detail page at the edge, before any JavaScript runs.

Detail pages are the one route the prerender cannot cover — there are 38k+ of
them and they change daily — so they were served as `app-shell.html`: no title,
no description, no canonical, no Product JSON-LD. The API's `sitemap.xml`
advertises every one of them, so the site's entire long tail looked like the
same empty document to a crawler. Google does render JavaScript, but render
budget is the constraint on a young domain with tens of thousands of URLs, and
merchant/rich results are driven by that JSON-LD specifically.

A Pages Function is matched **before** static assets and `_redirects`, so this
intercepts the route. The `/bikes/*` line in `public/_redirects` stays as the
fallback for a deployment where Functions are unavailable.

Four things are load-bearing:

- **It fails open.** Any timeout, non-200 or malformed response returns the
  unmodified shell with a 200 — today's behaviour. Only an explicit 404 from the
  API produces a 404, because an API outage must not de-index the catalogue.
- **404 means 404.** A missing bike returns a real 404 status. This is the
  proper fix for the soft 404s that `BikeDetailPage` previously handled by
  rendering a client-side `noindex` and hoping Googlebot executed it. That
  fallback is still there; a crawler now also gets the status on the first byte.
- **Everything injected is escaped.** Titles come from 97 scraped shops.
  Attributes go through `escapeAttr`, and the JSON-LD through `serializeJsonLd`,
  which neutralises `<` so a product title containing `</script>` cannot break
  out of the block.
- **Injection uses replacer functions, never replacement strings.** `$1`–`$9`
  and `$&` are substitution patterns inside a `String.replace` replacement, and
  bike descriptions contain prices. The first version expanded `$100` into
  capture group 1 and spliced the matched tag into its own content.

Meta and JSON-LD come from `src/lib/bikeMeta.js`, which the React page uses too,
so the pre-JS head and the client-rendered head cannot drift. That module carries
the same constraint as `content/guides.js` and `lib/landing.js` — no JSX, no
imports, no `import.meta.env` — because it also runs in the Workers runtime, and
it must be imported with an explicit `.js` extension so bare `node` can load it
in `test/`.

Tags injected here are marked `data-prerendered` and stripped by `main.jsx` on
mount, so React's own tags do not end up duplicated. **Anything stripped must be
re-declared by the mounting component** — including in `BikeDetailPage`'s error
branch, which would otherwise leave the page with no canonical at all after a
transient API failure.

Run it locally with `npm run preview:pages` (wrangler, port 8788) after a build;
`npm test` covers the function without a server.

---

## State management

Keep it simple. At this scale, **React Query (TanStack Query)** handles all server state:

- Fetch, cache, and re-fetch `/api/v1/bikes` based on filter params.
- Fetch and cache `/api/v1/meta/filters` once on page load.
- Built-in loading and error states.

No global state store (Zustand, Redux) is needed. Filter values live in URL query params — this gives shareable/bookmarkable URLs for free.

```
URL: /bikes?category=Mountain&size=M&size=L&min_discount=20
```

Derive filter state from `useSearchParams()` on mount; update URL on filter change.

---

## Routes

| Path | Page |
|---|---|
| `/` | `HomePage`: hero and finder, category tiles, today's deepest cuts, guide band, market strip |
| `/deals` | `DealsPage`: the feed, every category |
| `/road-bikes`, `/gravel-bikes`, `/mountain-bikes`, `/commuter-bikes`, `/electric-bikes` | `DealsPage` with the category pinned by the route, enumerated in `src/content/categories.js` |
| `/bikes/:id` | `BikeDetailPage`: the cross-shop comparison, size variants, spec coverage, price history |
| `/guides` | Guide hub: comparison table and cards, `pages/guides/` |
| `/guides/:type` | Five bike-type guides, enumerated in `src/content/guides.js` |
| `/trends` | `TrendsPage`: the market report |
| `/about`, `/contact`, `/data`, `/sitemap`, `/terms`, `/privacy` | Static pages |
| `/unsubscribe` | `UnsubscribePage`: posts the token from the email link |

The feed routes are the app shell (fixed chrome, one scrolling column).
Everything else renders inside `StaticLayout` or `HomeLayout` and scrolls
normally.

The feed has two layouts, chosen by `?view=`: cards for browsing, a table for
comparing. The table is the same query and the same filters, and its Now, Save
and Off columns are sort buttons. `view` is a URL parameter rather than component
state so a comparison survives a refresh and can be linked to; `useBikes` strips
it before the request, because it is not something the API is asked.

`ResultsToolbar` carries the result count, the sort, the layout toggle and a chip
row of everything currently narrowing the feed. The chips come from
`src/lib/chips.js`, which is import-free and unit-tested: each one carries the
params update that removes just itself, and the category pinned by the route is
deliberately not a chip.

The filter rail prints two things the API already knew and never showed. Each
facet's option count ("Any of 17") comes free from `/meta/filters`, which
excludes each facet from itself. Frame material and groupset print their
coverage, from `/meta/market`, because they are published on roughly three
fifths and one third of listings: filtering by either hides most of the
catalogue, and a filter that does that quietly is worse than one that says so.
The card and the table say the same thing per listing, with a dashed "no spec
published" chip rather than an empty row.

Category is a route rather than a query parameter, so each one is a page a
crawler can reach and a canonical it can keep. `useBikeParams(lockedCategory)`
takes the category from the route on those paths, which is why the filter
sidebar has no category control: `components/CategoryBar` owns that choice and
switches routes, carrying the rest of the query string with it. `/` forwards any
URL still carrying a feed parameter (`?category=`, `?city=`, `?q=` and the rest)
to the matching feed route, so links indexed before the split still land.

Region is a header control (`components/RegionMenu`), not a gate. It used to be
a full-page picker on `/`, which meant the highest-authority URL on the site had
no content on it and returning visitors watched the landing markup get replaced
on every refresh. `src/lib/landing.js` is now only the storage key and the
reader; `DealsPage` applies a remembered region once, with `replace`, on a URL
that does not already name a city.

Guide pages wrap their content in `components/guides/GuideLayout`, which owns
the title/description/canonical block and the BreadcrumbList JSON-LD. Their deal
strips use `components/CatalogRail`, which overfetches and dedupes by
brand+model — every size and store of the same bike is its own row, so an
undeduped top-4 on a narrow query renders four copies of one bike. The rail's
CTA link renders unconditionally, because the prerender never fetches and that
link is the only part of the strip a crawler ever sees.

---

## Component tree

The layout is a fixed shell: header and filter sidebar stay pinned, and only the
bike grid scrolls.

```
App
├── Header                    ← wordmark, nav, region control, search, saved count
├── CategoryBar               ← the seam: retail chrome above, the tool below
├── FilterSidebar (fixed)
│   ├── region + added-since buttons
│   ├── MultiSelectDropdown   ← city, size, shop, brand, material, groupset
│   ├── price range
│   └── minimum discount
├── BikeGrid (scroll container)
│   ├── ResultsToolbar        ← count, sort, grid/table toggle, applied-filter chips
│   ├── BikeCard (xN)         ← image, discount, price, saving, spec chips, cross-shop strip
│   ├── BikeTable             ← the same rows as columns, sortable
│   └── Prev / Next controls
├── SidebarAd
├── BackToTop
├── Footer
└── ErrorBoundary             ← wraps the tree
```

Supporting modules: `hooks/` (`useBikes`, `useFilters`, `useStats`, `useMarket`,
`usePins`), `api/client.js`, `lib/` (`badges`, `chips`, `market`, `scroll`,
`time`, `urls`), `content/` (`categories`, `guides`), `logos.js`, `seo.js`.

```
BikeDetailPage
├── price, stock and size matrix   ← every size of this model, with its price
├── spec list                      ← prints the gaps as "not published"
├── offers table                   ← same product at other shops, cheapest first
├── PriceHistoryChart              ← recharts, from /price-history
├── guide callout                  ← the category's guide
└── RelatedBikes
```

The detail page is a comparison, not a product page: BikeGrid sells nothing, and
the reason to look a bike up here rather than on Google is that the same product
is often at several shops at once. So the spread between the cheapest and the
dearest offer is named above the table, the offers table is the largest thing on
the page, and the spec list prints "Not published by this shop" rather than
dropping the row. `PriceHistoryChart` does the same with a single observation:
most listings have never been seen to change, and "tracked since 5 Aug, no
change since" is a real answer, where a drawn flat line implies a trend that is
not there.

---

## Pagination

**Offset pagination**, as planned: Prev/Next controls under the results, with
`offset` in the URL so a position is shareable. Changing any filter
clears `offset` (see `useBikes.js`); changing `offset` itself does not. Page
changes scroll the grid container back to the top rather than the window, because
the shell is fixed.

Infinite scroll was considered and not adopted — it loses shareable position, and
nothing so far suggests users want it.

---

## BikeCard

Dense information per card, responsive between a desktop list row and a mobile
card. Beyond the core fields, cards surface badges derived in `lib/badges.js` from
`price_drop_at` / `discount_started_at` (price drop, new deal) and
`sku_vendor_count` ("available at N shops", shown only when ≥ 2).

Clicking through calls `POST /bikes/{id}/click` before opening `product_url` in a
new tab; that counter backs the `clicks_desc` sort.

**One card is one product.** The API collapses a shop's size and colour variants
into a single result carrying a `sizes` list (see
[`api-design.md`](api-design.md)), so the card renders a chip row instead of the
same bike again at another size. The rules the card follows:

- A single size stays in the spec line as `Size M`. A lone chip reads as a
  filter button, and none of the chips are pressable.
- At most `MAX_SIZE_CHIPS` (5) chips, then a `+N` — enough for a size run
  without wrapping to a third line on a phone.
- The full list goes to screen readers as one `sr-only` sentence; the chips
  themselves are `aria-hidden`, so the row is read as "Sizes available: S, M, L"
  rather than as three orphaned letters.
- The card links and the "View deal" CTA point at the cheapest variant, which is
  also the one whose price the card headlines.

---

## Performance

At 500–5,000 results with a 50-record page size, performance is not a concern. If you add infinite scroll and load thousands of DOM nodes, use **TanStack Virtual** (windowed rendering). Not needed until you observe jank.

Image loading:
- Always set `loading="lazy"` on bike images.
- Set explicit `width` and `height` on `<img>` to avoid layout shift (CLS).
- If `image_url` is null, show a placeholder (grey box with a bicycle icon).

---

## What the original plan is missing

1. **URL-based filter state** — filters must be in the URL or users can't share searches.
2. **Loading and error states** — every fetch can fail or be slow; the UI must handle both.
3. **Empty state** — "No deals match your filters" with a clear-filters CTA.
4. **Mobile layout** — the dense grid is desktop-first; mobile needs a different layout mode.
5. **Image null handling** — `image_url` can be null per the data model; the UI must handle it.
6. ~~**Variant grouping**~~ — done. Grouping happens in the API rather than the
   grid, so `total`, the pager and the header's "N bikes" all count cards rather
   than variants; the client would only have deduped the 50 rows it was handed.
   See **BikeCard** above.
