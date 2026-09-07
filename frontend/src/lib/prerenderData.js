// Which API responses each prerendered route needs, keyed exactly as the hooks
// that render it will ask for them. scripts/prerender.js fetches these at build
// time and seeds them into the React Query cache before renderToString, so the
// shop pages ship their numbers and the feeds ship their cards instead of a
// dash and a skeleton.
//
// A route not listed here prerenders as before: its empty-data shape. That is
// also what every route gets when the API is unreachable at build time, so
// nothing here can fail a build.
//
// Loaded by bare node in test/prerender-data.test.js, hence the .js suffixes
// and no imports beyond the dependency-free lib and content modules.

import { CATEGORIES } from '../content/categories.js'
import { shopBySlug } from '../content/shops.js'
import {
  bikeQueryParams,
  filterQueryParams,
  homeDealsParams,
  readBikeParams,
  shopDealsParams,
  shopFacetParams,
} from './queries.js'

const stats = () => ({ queryKey: ['stats'], path: '/api/v1/meta/stats' })
const market = () => ({ queryKey: ['market'], path: '/api/v1/meta/market' })
const vendors = () => ({ queryKey: ['vendors'], path: '/api/v1/vendors' })

function bikes(params) {
  return { queryKey: ['bikes', params], path: '/api/v1/bikes', params }
}

function filters(params) {
  const shaped = filterQueryParams(params)
  return { queryKey: ['filters', shaped], path: '/api/v1/meta/filters', params: shaped }
}

// The feed at its URL with no query string: what a crawler, and a first visit,
// actually lands on. A visitor who arrives with ?city= gets a client fetch.
function feed(lockedCategory) {
  const params = bikeQueryParams(readBikeParams(new URLSearchParams(), lockedCategory))
  return [bikes(params), filters(params), stats(), market()]
}

const SHOP_ROUTE = /^\/shops\/([^/]+)$/

export function prerenderQueries(route) {
  if (route === '/') return [stats(), filters({}), market(), bikes(homeDealsParams())]
  if (route === '/deals') return feed(null)

  const category = CATEGORIES.find((c) => c.path === route)
  if (category) return feed(category.category)

  if (route === '/trends') return [market()]
  if (route === '/shops') return [vendors()]

  const slug = route.match(SHOP_ROUTE)?.[1]
  const shop = slug ? shopBySlug(slug) : null
  if (shop) {
    return [
      vendors(),
      filters(shopFacetParams(shop.name)),
      bikes(shopDealsParams(shop.name)),
    ]
  }

  return []
}
