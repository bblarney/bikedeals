// Query keys and request parameters, defined once.
//
// Two things read the API: the React Query hooks in the browser, and
// scripts/prerender.js at build time, which fetches the same responses and
// seeds them into the cache before rendering. A seed only helps if its key is
// exactly what the hook will ask for, so the shaping lives here and both sides
// import it. A page that builds its own params inline for useBikes still works
// in the browser; it just will not be prerendered with data.
//
// Dependency-free on purpose: the prerender's test loads this with bare node,
// outside Vite, so no JSX, no imports of hooks, no import.meta.env.

export const DEFAULT_SORT = 'discount_desc'
export const FEED_LIMIT = 48

// How many cards the home page and a shop page show under their headings.
export const HOME_DEAL_LIMIT = 4
export const SHOP_DEAL_LIMIT = 8

// The feed's parameters, read from a URL's query string. `lockedCategory`
// comes from the route: /road-bikes is the category, so it is not in the
// query string and the sidebar does not offer to change it.
export function readBikeParams(params, lockedCategory = null) {
  const get = (key, fallback = '') => params.get(key) ?? fallback
  const getAll = (key) => params.getAll(key)
  const getInt = (key, fallback = 0) => parseInt(params.get(key) ?? fallback, 10)

  return {
    category: lockedCategory ? [lockedCategory] : getAll('category'),
    city: getAll('city'),
    size: getAll('size'),
    vendor: getAll('vendor'),
    brand: getAll('brand'),
    frame_material: getAll('frame_material'),
    drivetrain_groupset: getAll('drivetrain_groupset'),
    min_discount: getInt('min_discount', 0),
    min_price: get('min_price'),
    max_price: get('max_price'),
    q: get('q'),
    added_since: get('added_since'),
    sort: get('sort', DEFAULT_SORT),
    // Grid or table. A URL preference rather than component state, so a
    // comparison view survives a refresh and can be linked to.
    view: get('view', 'grid') === 'table' ? 'table' : 'grid',
    offset: getInt('offset', 0),
    limit: FEED_LIMIT,
    sku: get('sku'),
    product_key: get('product_key'),
    lockedCategory,
  }
}

// What actually goes to /api/v1/bikes: everything the feed reads except the
// bits that only mean something to the UI.
export function bikeQueryParams(bikeParams) {
  const {
    update: _update,
    filterByProduct: _filterByProduct,
    lockedCategory: _lockedCategory,
    view: _view,
    ...queryParams
  } = bikeParams
  return queryParams
}

export function bikeQueryKey(bikeParams) {
  return ['bikes', bikeQueryParams(bikeParams)]
}

// The facet endpoint takes the filters, not the paging or the sort.
const FILTER_KEYS = [
  'category',
  'city',
  'size',
  'vendor',
  'brand',
  'frame_material',
  'drivetrain_groupset',
  'min_discount',
  'min_price',
  'max_price',
  'q',
  'added_since',
]

export function filterQueryParams(params) {
  const out = {}
  for (const key of FILTER_KEYS) out[key] = params?.[key]
  return out
}

export function filterQueryKey(params) {
  return ['filters', filterQueryParams(params)]
}

export function homeDealsParams() {
  return { sort: DEFAULT_SORT, limit: HOME_DEAL_LIMIT, offset: 0 }
}

export function shopDealsParams(vendorName) {
  return { vendor: [vendorName], min_discount: 1, sort: DEFAULT_SORT, limit: SHOP_DEAL_LIMIT }
}

export function shopFacetParams(vendorName) {
  return { vendor: [vendorName] }
}

// Serialise request parameters the one way the API expects: empty values are
// dropped, arrays repeat the key. Shared by the browser client and the
// prerender so the two cannot produce different URLs for the same key.
export function queryString(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    if (Array.isArray(v)) v.forEach((i) => search.append(k, i))
    else search.set(k, v)
  })
  const s = search.toString()
  return s ? `?${s}` : ''
}
