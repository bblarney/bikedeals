// Tests for the applied-filter chip row in src/lib/chips.js.
//
// Same arrangement as market-transforms.test.js: the module is import-free so
// the bare node runner can load it. What matters here is not the labels but the
// `clear` payloads, because a chip that removes the wrong thing silently widens
// or narrows the feed under the visitor.
//
// Run with `npm test`.

import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { activeChips } = await import('../src/lib/chips.js')

const params = (over = {}) => ({
  category: [], city: [], size: [], vendor: [], brand: [],
  frame_material: [], drivetrain_groupset: [],
  min_discount: 0, min_price: '', max_price: '', q: '', added_since: '',
  lockedCategory: null,
  ...over,
})

describe('activeChips', () => {
  test('no filters produces no chips', () => {
    assert.deepEqual(activeChips(params()), [])
  })

  test('each value of a repeatable filter gets its own chip', () => {
    const chips = activeChips(params({ city: ['Melbourne', 'Sydney'] }))
    assert.deepEqual(chips.map((c) => c.label), ['Melbourne', 'Sydney'])
  })

  test('clearing one value keeps the others', () => {
    const chips = activeChips(params({ city: ['Melbourne', 'Sydney', 'Perth'] }))
    assert.deepEqual(chips[1].clear, { city: ['Melbourne', 'Perth'] })
  })

  test('the route category is not a chip', () => {
    // On /gravel-bikes the category is the page, not a filter you can drop.
    const chips = activeChips(params({ category: ['Gravel'], lockedCategory: 'Gravel' }))
    assert.deepEqual(chips, [])
  })

  test('a category chosen by query string still is one', () => {
    const chips = activeChips(params({ category: ['Gravel'] }))
    assert.deepEqual(chips.map((c) => c.label), ['Gravel'])
  })

  test('a price range is one chip that clears both ends', () => {
    const chips = activeChips(params({ min_price: '2000', max_price: '6000' }))
    assert.equal(chips.length, 1)
    assert.equal(chips[0].label, '$2,000 to $6,000')
    assert.deepEqual(chips[0].clear, { min_price: '', max_price: '' })
  })

  test('an open-ended price range reads as one bound', () => {
    assert.equal(activeChips(params({ max_price: '3000' }))[0].label, 'Under $3,000')
    assert.equal(activeChips(params({ min_price: '3000' }))[0].label, 'From $3,000')
  })

  test('a zero minimum discount is not a filter', () => {
    assert.deepEqual(activeChips(params({ min_discount: 0 })), [])
  })

  test('min discount clears back to zero, not to empty', () => {
    // The slider reads a number; '' would render as NaN%.
    const [chip] = activeChips(params({ min_discount: 25 }))
    assert.equal(chip.label, '25% off or more')
    assert.deepEqual(chip.clear, { min_discount: 0 })
  })

  test('every chip carries a unique key', () => {
    const chips = activeChips(params({
      city: ['Melbourne'], size: ['M', 'L'], brand: ['Giant'],
      min_discount: 25, max_price: '6000', q: 'carbon', added_since: 'week',
    }))
    const keys = chips.map((c) => c.key)
    assert.equal(new Set(keys).size, keys.length)
  })

  test('missing params object is treated as no filters', () => {
    assert.deepEqual(activeChips(undefined), [])
  })
})
