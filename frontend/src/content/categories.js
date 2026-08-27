// The five categories, in one place: the category bar, the home page tiles, the
// footer, the guide cross-links and the ROUTES list in scripts/prerender.js all
// read from here, so adding a category cannot leave one of them behind.
//
// `category` is the value the API filters on; `path` is the URL a human sees.
// The two differ deliberately: "E-Bike" is a database value and /electric-bikes
// is a page.
//
// Deliberately dependency-free, for the same reason content/guides.js is:
// prerender.js imports this with bare `node`, outside Vite. No JSX, no imports,
// no import.meta.env.

export const CATEGORIES = [
  {
    slug: 'road-bikes',
    path: '/road-bikes',
    category: 'Road',
    label: 'Road',
    plural: 'Road bikes',
    blurb: 'Sealed roads, low and fast',
  },
  {
    slug: 'gravel-bikes',
    path: '/gravel-bikes',
    category: 'Gravel',
    label: 'Gravel',
    plural: 'Gravel bikes',
    blurb: 'One bike that does most things',
  },
  {
    slug: 'mountain-bikes',
    path: '/mountain-bikes',
    category: 'Mountain',
    label: 'Mountain',
    plural: 'Mountain bikes',
    blurb: 'Trails, rocks, roots, descents',
  },
  {
    slug: 'commuter-bikes',
    path: '/commuter-bikes',
    category: 'Commuter',
    label: 'Commuter',
    plural: 'Commuter bikes',
    blurb: 'Short trips in normal clothes',
  },
  {
    slug: 'electric-bikes',
    path: '/electric-bikes',
    category: 'E-Bike',
    label: 'Electric',
    plural: 'Electric bikes',
    blurb: 'Hills, cargo, longer trips',
  },
]

export const CATEGORY_PATHS = CATEGORIES.map((c) => c.path)

export function categoryFor(value) {
  return CATEGORIES.find((c) => c.category === value) ?? null
}

// The page for a category, optionally carrying a query string. Guides link here
// with a ?q= already attached, so `search` is appended rather than replacing.
export function categoryPath(value, search = '') {
  const entry = categoryFor(value)
  if (!entry) return `/deals${search ? `?${search.replace(/^\?/, '')}` : ''}`
  return `${entry.path}${search ? `?${search.replace(/^\?/, '')}` : ''}`
}
