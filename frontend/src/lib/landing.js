// The landing-page/deal-feed gate, in one place.
//
// `/` renders two different things: the landing page for a first-time visitor,
// the deal feed for anyone who has already picked a region or arrived on a
// city-filtered URL. The prerendered `/` can only be one of them, and it is the
// landing page — a crawler has neither localStorage nor a query string, so that
// is the version it should see.
//
// Which means a returning visitor is served landing markup and then watches
// React replace it with the feed: a flash of the wrong page on every refresh.
// DEAL_FEED_GATE runs in the head of that prerendered page and hides the
// landing markup before it can paint, for exactly the visitors who are about to
// get the feed instead.
//
// Bare `node` loads this file from scripts/prerender.js, outside Vite: no JSX,
// no imports, no `import.meta.env`.

export const REGION_KEY = 'bikegrid_region'

// Guarded because this also runs during the build-time prerender, where there
// is no localStorage — and in a browser that blocks storage access entirely.
export function hasStoredRegion() {
  try {
    return !!localStorage.getItem(REGION_KEY)
  } catch {
    return false
  }
}

// Inlined into the prerendered `/` by scripts/prerender.js, and evaluated
// before `#root` is parsed. The condition mirrors `showLanding` in App.jsx
// inverted — keep the two in step, or the gate hides the page it should be
// showing.
export const DEAL_FEED_GATE = `try{if(localStorage.getItem('${REGION_KEY}')||new URLSearchParams(location.search).getAll('city').length){document.documentElement.classList.add('deal-feed-boot')}}catch(e){}`

// Paired with the gate. `display:contents` keeps the wrapper out of layout for
// the visitor who does see the landing markup; the second rule wins on
// specificity for the visitor who shouldn't. The background stands in for the
// app's own `bg-gray-50` so the wait for the bundle isn't a white flash.
export const DEAL_FEED_GATE_STYLE =
  '#prerendered-landing{display:contents}' +
  'html.deal-feed-boot #prerendered-landing{display:none}' +
  'html.deal-feed-boot{background:#f9fafb}'
