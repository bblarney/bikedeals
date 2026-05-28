# Frontend Design

## Framework

**Decision: React** (Vite scaffold). State via TanStack Query (server state) with filter values stored in URL query params.

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

## Component tree

```
App
├── Header
│   ├── SiteName / logo
│   └── StatsBanner          ← "342 deals · 12 shops · last updated 2h ago"
├── FilterStrip (sticky)
│   ├── CityDropdown         ← primary filter; scopes all others
│   ├── CategoryDropdown
│   ├── SizeGrid             ← multi-select button grid (S / M / L / XL / XS)
│   ├── DiscountSlider       ← min discount %
│   ├── VendorDropdown
│   └── SearchInput
├── ResultsHeader            ← "342 deals found · sorted by discount"
├── BikeGrid
│   └── BikeCard (×n)
│       ├── BikeImage
│       ├── DiscountBadge    ← "29% off · Save $200"
│       ├── ModelInfo        ← Brand + Model, Size
│       ├── PriceDisplay     ← $499 (was $699)
│       ├── VendorTag        ← "Local Bike Shop"
│       └── CTAButton        ← "View Deal →" (opens product_url in new tab)
└── Pagination               ← or infinite scroll (see below)
```

---

## Pagination vs infinite scroll

| | Offset pagination | Infinite scroll |
|---|---|---|
| Shareable position | Yes (URL: `?offset=50`) | No |
| UX for deal hunting | Moderate | Better (keep scrolling) |
| Complexity | Low | Medium |

**Recommendation:** Start with offset pagination (simple, shareable links). Switch to infinite scroll if users complain about it feeling slow.

---

## BikeCard design

Dense information per card is the stated goal. Two layout options:

### Option A — Horizontal list row
```
[img 80×80] | Trek Marlin 5 · M   |  $499  ~~$699~~  | [29% OFF]  | Local Bike Shop | [View Deal →]
```
Maximizes vertical density. Good for desktop power users.

### Option B — Compact card grid
```
┌──────────────────┐
│  [img 200×150]   │
│  29% OFF · $200  │  ← discount badge
│  Trek Marlin 5   │
│  Size: M         │
│  $499 ~~$699~~   │
│  Local Bike Shop │
│  [View Deal →]   │
└──────────────────┘
```
Better for mobile. Familiar e-commerce pattern.

**Recommendation:** Build Option A (list row) for the desktop MVP; it shows more results above the fold and matches the "dense data" goal. Make it responsive to collapse into a card on mobile.

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
