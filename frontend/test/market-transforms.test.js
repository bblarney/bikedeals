// Tests for the /trends data transforms in src/lib/market.js.
//
// That module is deliberately free of imports so it can be loaded by the bare
// node runner here, the same way src/content/guides.js is loaded by the
// prerender script. The charts themselves need a browser to measure, but the
// reshaping between the API's flat point list and what recharts plots is pure,
// and that is where a wrong number would actually come from.
//
// Run with `npm test` (node's built-in runner; no new dependencies).

import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { pick, pivot, toShares, inOrder, groupsetBrand, feedHref, coverageShares } = await import(
  '../src/lib/market.js'
)

const point = (chart, bucket, bucket_rank, series, n, value = null) => ({
  chart, bucket, bucket_rank, series, n, value,
})

describe('pick', () => {
  test('selects one chart and preserves the API order', () => {
    const points = [
      point('a', 'x', 0, 's1', 1),
      point('b', 'x', 0, 's1', 2),
      point('a', 'y', 1, 's1', 3),
    ]
    assert.deepEqual(pick(points, 'a').map((p) => p.n), [1, 3])
  })
})

describe('pivot', () => {
  test('one row per bucket, one key per series', () => {
    const { rows, series } = pivot([
      point('m', 'Under $1k', 0, 'Carbon', 10),
      point('m', 'Under $1k', 0, 'Steel', 30),
      point('m', '$1–2k', 1, 'Carbon', 5),
    ])
    assert.deepEqual(series, ['Carbon', 'Steel'])
    assert.deepEqual(rows, [
      { bucket: 'Under $1k', _total: 40, Carbon: 10, Steel: 30 },
      { bucket: '$1–2k', _total: 5, Carbon: 5, Steel: 0 },
    ])
  })

  test('a series missing from a bucket becomes 0, never undefined', () => {
    // A hole in a stacked bar is worse than a zero-height segment: recharts
    // stacks undefined as a gap and the bar stops reaching 100%.
    const { rows } = pivot([
      point('m', 'a', 0, 'Carbon', 1),
      point('m', 'b', 1, 'Steel', 1),
    ])
    assert.equal(rows[0].Steel, 0)
    assert.equal(rows[1].Carbon, 0)
  })

  test('bucket order follows the API, not the alphabet', () => {
    const { rows } = pivot([
      point('m', 'Under $1k', 0, 's', 1),
      point('m', '$12k+', 6, 's', 1),
    ])
    assert.deepEqual(rows.map((r) => r.bucket), ['Under $1k', '$12k+'])
  })
})

describe('toShares', () => {
  test('each bucket sums to 100 percent and keeps its raw counts', () => {
    const { rows } = toShares(
      pivot([
        point('m', 'a', 0, 'Carbon', 1),
        point('m', 'a', 0, 'Steel', 3),
      ]),
    )
    assert.equal(rows[0].Carbon, 25)
    assert.equal(rows[0].Steel, 75)
    assert.equal(rows[0].Carbon_n, 1)
    assert.equal(rows[0]._total, 4)
  })

  test('an empty bucket is 0 percent rather than NaN', () => {
    const { rows } = toShares({ rows: [{ bucket: 'a', _total: 0, X: 0 }], series: ['X'] })
    assert.equal(rows[0].X, 0)
  })
})

describe('inOrder', () => {
  test('sorts to the fixed display order', () => {
    assert.deepEqual(
      inOrder(['Steel', 'Carbon', 'Aluminium'], ['Carbon', 'Aluminium', 'Steel']),
      ['Carbon', 'Aluminium', 'Steel'],
    )
  })

  test('an unknown series sorts last rather than being dropped', () => {
    const out = inOrder(['Mystery', 'Carbon'], ['Carbon', 'Steel'])
    assert.deepEqual(out, ['Carbon', 'Mystery'])
  })
})

describe('groupsetBrand', () => {
  test('reads the brand off the normalised groupset string', () => {
    assert.equal(groupsetBrand('Shimano Dura-Ace Di2'), 'Shimano')
    assert.equal(groupsetBrand('SRAM GX Eagle'), 'SRAM')
    assert.equal(groupsetBrand('Campagnolo Super Record'), 'Campagnolo')
  })
})

describe('feedHref', () => {
  test('turns a price band label back into the bounds the feed filters on', () => {
    assert.equal(
      feedHref({ category: 'Road', band: '$2–3k' }),
      '/?category=Road&min_price=2000&max_price=3000',
    )
  })

  test('the open-ended bands carry only the bound they have', () => {
    assert.equal(feedHref({ band: 'Under $1k' }), '/?max_price=1000')
    assert.equal(feedHref({ band: '$12k+' }), '/?min_price=12000')
  })

  test('an unknown band contributes no price filter at all', () => {
    // Better a broader feed than one silently filtered to the wrong range.
    assert.equal(feedHref({ category: 'Road', band: 'nonsense' }), '/?category=Road')
  })

  test('encodes values that need it, and falls back to the bare feed', () => {
    assert.equal(feedHref({ brand: 'Riese & Müller' }), '/?brand=Riese+%26+M%C3%BCller')
    assert.equal(feedHref({}), '/')
  })
})

describe('coverageShares', () => {
  test('reports each enrichment field as a percentage of all listings', () => {
    const shares = coverageShares({
      total_listings: 10000,
      coverage: { frame_material: 6000, drivetrain_groupset: 3300 },
    })
    assert.deepEqual(shares, { frame_material: 60, drivetrain_groupset: 33 })
  })

  test('returns null rather than dividing by a missing total', () => {
    assert.equal(coverageShares(undefined), null)
    assert.equal(coverageShares({ coverage: { frame_material: 5 } }), null)
    assert.equal(coverageShares({ total_listings: 0, coverage: {} }), null)
  })
})
