// Tests for src/lib/prerenderData.js and src/lib/queries.js: the contract that
// a seed the prerender fetches lands under the key the hook will ask for.
//
// A mismatch is silent in production: the page still renders, the hook still
// fetches, and the only symptom is that the prerendered HTML went back to
// dashes and skeletons. So the keys are checked here, against the same shaping
// functions the hooks use, rather than by eye in the built output.
//
// Same arrangement as the other suites: both modules only import the
// dependency-free lib and content files, so the bare node runner can load them.
//
// Run with `npm test`.

import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { prerenderQueries } = await import('../src/lib/prerenderData.js')
const {
  FEED_LIMIT,
  HOME_DEAL_LIMIT,
  SHOP_DEAL_LIMIT,
  bikeQueryKey,
  filterQueryKey,
  homeDealsParams,
  queryString,
  readBikeParams,
  shopDealsParams,
  shopFacetParams,
} = await import('../src/lib/queries.js')
const { SHOPS } = await import('../src/content/shops.js')
const { CATEGORIES } = await import('../src/content/categories.js')

// What useBikeParams returns for a URL: the read fields plus the two writers.
function feedParams(search, lockedCategory = null) {
  return {
    ...readBikeParams(new URLSearchParams(search), lockedCategory),
    update: () => {},
    filterByProduct: () => {},
  }
}

function keysOf(route) {
  return prerenderQueries(route).map((q) => JSON.stringify(q.queryKey))
}

function has(route, queryKey) {
  return keysOf(route).includes(JSON.stringify(queryKey))
}

describe('readBikeParams', () => {
  test('a bare URL reads to the feed defaults', () => {
    const p = readBikeParams(new URLSearchParams())
    assert.deepEqual(p.category, [])
    assert.equal(p.sort, 'discount_desc')
    assert.equal(p.limit, FEED_LIMIT)
    assert.equal(p.offset, 0)
    assert.equal(p.min_discount, 0)
    assert.equal(p.view, 'grid')
    assert.equal(p.lockedCategory, null)
  })

  test('a locked category is the category, and is not read from the URL', () => {
    const p = readBikeParams(new URLSearchParams('category=Gravel'), 'Road')
    assert.deepEqual(p.category, ['Road'])
    assert.equal(p.lockedCategory, 'Road')
  })

  test('repeatable filters repeat, and view is grid unless it says table', () => {
    const p = readBikeParams(new URLSearchParams('city=Sydney&city=Perth&view=table&offset=48'))
    assert.deepEqual(p.city, ['Sydney', 'Perth'])
    assert.equal(p.view, 'table')
    assert.equal(p.offset, 48)
  })
})

describe('bikeQueryKey', () => {
  test('drops the UI-only fields, keeps everything the API reads', () => {
    const [scope, params] = bikeQueryKey(feedParams('view=table'))
    assert.equal(scope, 'bikes')
    for (const gone of ['update', 'filterByProduct', 'lockedCategory', 'view']) {
      assert.equal(gone in params, false, `${gone} leaked into the key`)
    }
    assert.equal(params.limit, FEED_LIMIT)
    assert.equal(params.sort, 'discount_desc')
  })
})

describe('queryString', () => {
  test('drops empty values, repeats arrays, keeps zero', () => {
    const qs = queryString({ q: '', city: ['Sydney', 'Perth'], min_discount: 0, sort: 'x', n: null })
    assert.equal(qs, '?city=Sydney&city=Perth&min_discount=0&sort=x')
  })

  test('is empty for nothing', () => {
    assert.equal(queryString({}), '')
    assert.equal(queryString(), '')
  })
})

describe('prerenderQueries', () => {
  test('the home page is seeded with exactly what HomePage asks for', () => {
    assert.ok(has('/', ['stats']))
    assert.ok(has('/', ['market']))
    assert.ok(has('/', filterQueryKey({})))
    assert.ok(has('/', bikeQueryKey(homeDealsParams())))
    assert.equal(homeDealsParams().limit, HOME_DEAL_LIMIT)
  })

  test('/deals is seeded under the key useBikes derives from a bare URL', () => {
    assert.ok(has('/deals', bikeQueryKey(feedParams(''))))
    assert.ok(has('/deals', filterQueryKey(feedParams(''))))
  })

  test('every category route is seeded with its category locked', () => {
    for (const c of CATEGORIES) {
      assert.ok(
        has(c.path, bikeQueryKey(feedParams('', c.category))),
        `${c.path} feed key`,
      )
      assert.ok(
        has(c.path, filterQueryKey(feedParams('', c.category))),
        `${c.path} filters key`,
      )
      const bikes = prerenderQueries(c.path).find((q) => q.queryKey[0] === 'bikes')
      assert.deepEqual(bikes.params.category, [c.category])
    }
  })

  test('every shop page is seeded under the keys ShopDetailPage uses', () => {
    for (const shop of SHOPS) {
      assert.ok(has(shop.path, ['vendors']), `${shop.path} vendors`)
      assert.ok(has(shop.path, filterQueryKey(shopFacetParams(shop.name))), `${shop.path} facets`)
      assert.ok(has(shop.path, bikeQueryKey(shopDealsParams(shop.name))), `${shop.path} deals`)
    }
    assert.equal(shopDealsParams('x').limit, SHOP_DEAL_LIMIT)
  })

  test('the shops index and trends want one response each', () => {
    assert.deepEqual(keysOf('/shops'), [JSON.stringify(['vendors'])])
    assert.deepEqual(keysOf('/trends'), [JSON.stringify(['market'])])
  })

  test('static pages and unknown routes want nothing', () => {
    for (const route of ['/about', '/guides', '/guides/road-bikes', '/shops/no-such-shop', '/nope']) {
      assert.deepEqual(prerenderQueries(route), [], route)
    }
  })

  test('every query names a request the API serves, with a serialisable key', () => {
    for (const route of ['/', '/deals', '/road-bikes', '/shops', SHOPS[0].path]) {
      for (const q of prerenderQueries(route)) {
        assert.match(q.path, /^\/api\/v1\//, `${route}: ${q.path}`)
        assert.doesNotThrow(() => JSON.stringify(q.queryKey))
      }
    }
  })
})
