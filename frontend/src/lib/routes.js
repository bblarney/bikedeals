// Which URLs are the deal feed, and the trailing-slash tolerance that comparing
// them needs.
//
// Dependency-free apart from content/categories.js, which is itself plain JS, so
// the bare node test runner can load this. See test/feed-routes.test.js.

import { CATEGORY_PATHS } from '../content/categories.js'

// Every route that is the deal feed. They share one component and differ only
// in which category is pinned by the URL.
export const FEED_PATHS = ['/deals', ...CATEGORY_PATHS]

// Cloudflare Pages serves /deals from dist/deals/index.html and redirects the
// bare URL to the trailing-slash form, so a reload lands on "/deals/" while an
// in-app <Link to="/deals"> gives "/deals". React Router matches its routes
// either way; only string comparisons against a path see the difference, and on
// the feed that difference cost the fixed app shell and rendered the footer
// twice. Normalise before comparing, always.
export function normalizePath(pathname) {
  const trimmed = pathname.replace(/\/+$/, '')
  return trimmed === '' ? '/' : trimmed
}

export function isFeedPath(pathname) {
  return FEED_PATHS.includes(normalizePath(pathname))
}
