# Frontend Design

Reflects `frontend/src/`. When the code and this document disagree, the code wins.

## Framework

**React 19 + Vite + Tailwind CSS 4**, with TanStack Query for server state and
filter values in URL query params. Routing is `react-router-dom`; the price-history
chart uses `recharts`. No global state store — none has been needed.

---

## Deployment

The frontend is a static build (`vite build` → `dist/`). Deploy to Cloudflare Pages or Vercel. Both are free and provide instant global CDN.

The API URL must be an environment variable:
```
VITE_API_BASE_URL=https://api.bikegrid.example.com
```

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
| `/` | Main deal feed (`MainLayout`) |
| `/bikes/:id` | `BikeDetailPage` — offers, size variants, price history |
| `/about`, `/contact`, `/sitemap`, `/terms`, `/privacy` | Static pages |
| `/unsubscribe` | `UnsubscribePage` — posts the token from the email link |

Everything except `/` renders inside `StaticLayout`.

---

## Component tree

The layout is a fixed shell: header and filter sidebar stay pinned, and only the
bike grid scrolls.

```
App
├── Header                    ← logo, search, stats ("342 deals · 77 shops · updated 2h ago")
├── FilterSidebar (fixed)
│   ├── MultiSelectDropdown   ← city, category, brand, vendor, material, groupset
│   ├── size chips            ← multi-select
│   ├── price + discount ranges
│   └── added-since control
├── BikeGrid (scroll container)
│   ├── BikeCard (×n)         ← image, discount badge, model, size, price, vendor, CTA
│   └── Prev / Next controls  ← top and bottom of the list
├── SidebarAd
├── BackToTop
├── Footer
└── ErrorBoundary             ← wraps the tree

BikeDetailPage
├── offers table              ← same SKU at other shops, cheapest first
├── size variants
├── PriceHistoryChart         ← recharts, from /price-history
└── RelatedBikes
```

Supporting modules: `hooks/` (`useBikes`, `useFilters`, `useStats`, `usePins`),
`api/client.js`, `lib/` (`badges`, `scroll`, `time`), `logos.js`, `seo.js`.

---

## Pagination

**Offset pagination**, as planned — Prev/Next controls rendered at both ends of
the grid, with `offset` in the URL so a position is shareable. Changing any filter
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
6. **Variant grouping** — if one row per size, the grid needs to group or dedupe cards by model so users don't see 5 identical Trek Marlin 5 cards with different sizes.
