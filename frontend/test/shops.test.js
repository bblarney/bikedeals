// Tests for src/lib/shops.js, the shops tab's arithmetic.
//
// The case that matters is the chain split. A chain stores one catalogue row per
// city, so ?city=Melbourne does NOT narrow its listing count: 99 Bikes reports
// 468 nationally and the same 468 in Melbourne. Ranking chains alongside local
// shops in a city view therefore puts a national number above every real
// Melbourne shop, which is why partitionByCity exists.
//
// Same arrangement as the other suites here: lib/shops.js only imports
// content/shops.js, which is generated and dependency-free, so the bare node
// runner can load it.
//
// Run with `npm test`.

import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const {
  cityCounts,
  mergeShops,
  ordinal,
  partitionByCity,
  rankInCity,
  rankShops,
  shopTotals,
  shopWhere,
} = await import('../src/lib/shops.js')
const { SHOPS, isNational, servesCity } = await import('../src/content/shops.js')

// Real names from the generated registry, so a rename that breaks the join
// breaks this suite rather than the page.
const LOCAL = 'Bike Zone Fitzroy'   // Melbourne, one storefront
const LOCAL_2 = 'Fitzroy Cycles'    // Melbourne, one storefront
const CHAIN = '99 Bikes'            // 8 cities, including Melbourne
const ONLINE = 'Canyon'             // no city at all

function vendor(name, listings, onSale, deepest = 0, lastSuccessAt = null) {
  return {
    vendor_name: name,
    listings,
    on_sale: onSale,
    deepest_cut: deepest,
    last_success_at: lastSuccessAt,
  }
}

describe('the generated registry', () => {
  test('carries the shops the rest of this suite joins against', () => {
    for (const name of [LOCAL, LOCAL_2, CHAIN, ONLINE]) {
      assert.ok(SHOPS.some((s) => s.name === name), `${name} missing from content/shops.js`)
    }
  })

  test('slugs are unique, so no shop page shadows another', () => {
    assert.equal(new Set(SHOPS.map((s) => s.slug)).size, SHOPS.length)
  })

  test('a chain and an online seller are both national, a storefront is not', () => {
    const by = (name) => SHOPS.find((s) => s.name === name)
    assert.equal(isNational(by(CHAIN)), true)
    assert.equal(isNational(by(ONLINE)), true)
    assert.equal(isNational(by(LOCAL)), false)
  })

  test('a shop with no city serves every city', () => {
    assert.equal(servesCity(SHOPS.find((s) => s.name === ONLINE), 'Melbourne'), true)
    assert.equal(servesCity(SHOPS.find((s) => s.name === LOCAL), 'Sydney'), false)
  })
})

describe('mergeShops', () => {
  test('joins API counts to registry metadata and derives the share', () => {
    const [row] = mergeShops([vendor(LOCAL, 93, 81, 69)])
    assert.equal(row.name, LOCAL)
    assert.equal(row.slug, 'bike-zone-fitzroy')
    assert.equal(row.path, '/shops/bike-zone-fitzroy')
    assert.equal(row.share, 87) // 81/93 = 87.1%
    assert.equal(row.national, false)
  })

  test('drops a vendor that is no longer in the registry', () => {
    // A retired shop can still have rows in the feed, and it has no slug, so
    // there is no page to link a row to.
    assert.deepEqual(mergeShops([vendor('George\'s Bike Shop', 10, 5)]), [])
  })

  test('a shop with no listings gets a zero share, not a divide by zero', () => {
    const [row] = mergeShops([vendor(LOCAL, 0, 0)])
    assert.equal(row.share, 0)
    assert.ok(Number.isFinite(row.share))
  })

  test('a shop with stock but nothing discounted survives with a zero share', () => {
    const [row] = mergeShops([vendor(LOCAL, 11, 0, 0)])
    assert.equal(row.listings, 11)
    assert.equal(row.share, 0)
    assert.equal(row.deepestCut, 0)
  })
})

describe('partitionByCity', () => {
  const rows = mergeShops([
    vendor(LOCAL, 93, 81, 69),
    vendor(LOCAL_2, 49, 37, 44),
    vendor(CHAIN, 468, 462, 49),
    vendor(ONLINE, 62, 22, 41),
  ])

  test('keeps a chain out of the local ranking even though it serves the city', () => {
    const { local, national } = partitionByCity(rows, 'Melbourne')
    assert.deepEqual(local.map((r) => r.name).sort(), [LOCAL, LOCAL_2].sort())
    assert.deepEqual(national.map((r) => r.name).sort(), [CHAIN, ONLINE].sort())
  })

  test('a city the local shops do not serve keeps only the national sellers', () => {
    const { local, national } = partitionByCity(rows, 'Perth')
    assert.deepEqual(local, [])
    // Canyon ships anywhere; 99 Bikes has no Perth store in its YAML.
    assert.deepEqual(national.map((r) => r.name), [ONLINE])
  })

  test('with no city, every shop is kept and only the kind decides the band', () => {
    const { local, national } = partitionByCity(rows, null)
    assert.equal(local.length + national.length, rows.length)
    assert.equal(national.length, 2)
  })
})

describe('rankShops', () => {
  const rows = mergeShops([
    vendor(LOCAL, 93, 81, 69),      // 87%
    vendor(LOCAL_2, 49, 37, 44),    // 76%
    vendor(CHAIN, 468, 462, 49),    // 99%
  ])

  test('share puts the most-discounted range first', () => {
    assert.deepEqual(rankShops(rows, 'share').map((r) => r.name), [CHAIN, LOCAL, LOCAL_2])
  })

  test('deepest cut is a different order from share', () => {
    assert.deepEqual(rankShops(rows, 'deepest').map((r) => r.name), [LOCAL, CHAIN, LOCAL_2])
  })

  test('listings ranks by size', () => {
    assert.deepEqual(rankShops(rows, 'listings').map((r) => r.name), [CHAIN, LOCAL, LOCAL_2])
  })

  test('a tie on share breaks on the absolute count, not on input order', () => {
    // 4 of 4 and 462 of 468 both round to a high share; the bigger shop wins.
    const tied = mergeShops([vendor('Lekker Bikes', 4, 4, 17), vendor(CHAIN, 462, 462, 49)])
    assert.deepEqual(rankShops(tied, 'share').map((r) => r.name), [CHAIN, 'Lekker Bikes'])
  })

  test('does not mutate its input', () => {
    const before = rows.map((r) => r.name)
    rankShops(rows, 'listings')
    assert.deepEqual(rows.map((r) => r.name), before)
  })

  test('an unknown sort falls back to name rather than throwing', () => {
    assert.deepEqual(rankShops(rows, 'nonsense').map((r) => r.name), [CHAIN, LOCAL, LOCAL_2].sort())
  })
})

describe('cityCounts', () => {
  test('counts every shop that serves a city, chains included', () => {
    const rows = mergeShops([vendor(LOCAL, 93, 81), vendor(CHAIN, 468, 462)])
    const melbourne = cityCounts(rows).find((c) => c.city === 'Melbourne')
    assert.equal(melbourne.shops, 2)
  })

  test('a shop with no city creates no chip of its own', () => {
    assert.deepEqual(cityCounts(mergeShops([vendor(ONLINE, 62, 22)])), [])
  })

  test('a ships-anywhere shop is counted in every city that has a chip', () => {
    // Regression: the chip read 22 while the page it opened was headed "23
    // shops serving Melbourne", because servesCity includes the online sellers
    // and this did not.
    const rows = mergeShops([vendor(LOCAL, 93, 81), vendor(ONLINE, 62, 22)])
    const counts = cityCounts(rows)
    const melbourne = counts.find((c) => c.city === 'Melbourne')
    const { local, national } = partitionByCity(rows, 'Melbourne')
    assert.equal(melbourne.shops, 2)
    assert.equal(melbourne.shops, local.length + national.length)
  })

  test('every chip agrees with what its own city page will show', () => {
    const rows = mergeShops([
      vendor(LOCAL, 93, 81), vendor(LOCAL_2, 49, 37),
      vendor(CHAIN, 468, 462), vendor(ONLINE, 62, 22),
    ])
    for (const { city, shops } of cityCounts(rows)) {
      const { local, national } = partitionByCity(rows, city)
      assert.equal(shops, local.length + national.length, city)
    }
  })

  test('sorts by shop count, most first', () => {
    const counts = cityCounts(mergeShops([
      vendor(LOCAL, 1, 1), vendor(LOCAL_2, 1, 1), vendor(CHAIN, 1, 1),
    ]))
    assert.equal(counts[0].city, 'Melbourne')
    assert.equal(counts[0].shops, 3)
  })
})

describe('rankInCity', () => {
  const rows = mergeShops([
    vendor(LOCAL, 93, 81, 69),
    vendor(LOCAL_2, 49, 37, 44),
    vendor(CHAIN, 468, 462, 49),
  ])

  test('ranks a local shop among local shops only', () => {
    const row = rows.find((r) => r.name === LOCAL)
    // 99 Bikes outranks it on share but is not in the local ranking at all.
    assert.deepEqual(rankInCity(rows, row), { position: 1, total: 2, city: 'Melbourne' })
  })

  test('is null for a chain, which has no single city to rank in', () => {
    assert.equal(rankInCity(rows, rows.find((r) => r.name === CHAIN)), null)
  })
})

describe('shopTotals and labels', () => {
  test('sums listings and takes the deepest cut across shops', () => {
    const totals = shopTotals(mergeShops([
      vendor(LOCAL, 93, 81, 69), vendor(LOCAL_2, 49, 37, 44),
    ]))
    assert.deepEqual(totals, { shops: 2, listings: 142, onSale: 118, deepestCut: 69 })
  })

  test('shopWhere names a city, counts a chain, and says so for online only', () => {
    assert.equal(shopWhere({ cities: ['Melbourne'] }), 'Melbourne')
    assert.equal(shopWhere({ cities: ['Melbourne', 'Sydney'] }), '2 cities')
    assert.equal(shopWhere({ cities: [] }), 'Ships anywhere')
  })

  test('ordinal handles the teens', () => {
    assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22].map(ordinal),
      ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd'])
  })
})
