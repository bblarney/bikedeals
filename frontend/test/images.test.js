// Tests for the Shopify image sizing helper in src/lib/images.js.
//
// Same arrangement as the other suites here: the module is import-free, so the
// bare node runner can load it. The cases that matter are the query-string
// shapes the scraped URLs actually come in, and the rule that only
// cdn.shopify.com is ever rewritten.
//
// Run with `npm test`.

import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { shopImage } = await import('../src/lib/images.js')

describe('shopImage', () => {
  test('adds width to a Shopify URL that already has a version param', () => {
    assert.equal(
      shopImage('https://cdn.shopify.com/s/files/1/x/IMG.jpg?v=123', 600),
      'https://cdn.shopify.com/s/files/1/x/IMG.jpg?v=123&width=600',
    )
  })

  test('adds width to a Shopify URL with no query string', () => {
    assert.equal(
      shopImage('https://cdn.shopify.com/s/files/1/x/IMG.jpg', 120),
      'https://cdn.shopify.com/s/files/1/x/IMG.jpg?width=120',
    )
  })

  test('overwrites a width that is already present', () => {
    assert.equal(
      shopImage('https://cdn.shopify.com/s/files/1/x/IMG.jpg?width=99', 600),
      'https://cdn.shopify.com/s/files/1/x/IMG.jpg?width=600',
    )
  })

  test('leaves a non-Shopify URL untouched', () => {
    const url = 'https://www.happywheels.com.au/media/IMG.jpg'
    assert.equal(shopImage(url, 600), url)
  })

  test('leaves a falsy value untouched', () => {
    assert.equal(shopImage(null, 600), null)
    assert.equal(shopImage('', 600), '')
    assert.equal(shopImage(undefined, 600), undefined)
  })

  test('leaves a non-URL string untouched rather than throwing', () => {
    assert.equal(shopImage('not a url', 600), 'not a url')
  })
})
