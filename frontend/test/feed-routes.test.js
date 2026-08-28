// Tests for src/lib/routes.js, which decides whether a URL is the deal feed.
//
// Same arrangement as the other suites here: the module only imports
// content/categories.js, which is dependency-free, so the bare node runner can
// load it.
//
// The case that matters is the trailing slash. Cloudflare Pages redirects
// /deals to /deals/, so a reload takes the slashed form while an in-app link
// takes the bare one. When the two disagreed, a reloaded feed lost its fixed
// shell (the whole document scrolled instead of the grid column) and rendered
// the footer twice.
//
// Run with `npm test`.

import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { isFeedPath, normalizePath, FEED_PATHS } = await import('../src/lib/routes.js')

describe('isFeedPath', () => {
  test('matches the feed routes as an in-app link writes them', () => {
    for (const path of FEED_PATHS) {
      assert.equal(isFeedPath(path), true, path)
    }
  })

  test('matches the same routes as a reload lands on them', () => {
    for (const path of FEED_PATHS) {
      assert.equal(isFeedPath(`${path}/`), true, `${path}/`)
    }
  })

  test('covers every category route', () => {
    assert.ok(FEED_PATHS.includes('/deals'))
    assert.ok(FEED_PATHS.includes('/gravel-bikes'))
    assert.ok(FEED_PATHS.includes('/electric-bikes'))
    assert.equal(FEED_PATHS.length, 6)
  })

  test('rejects routes that keep normal document scrolling', () => {
    for (const path of ['/', '/about', '/trends', '/guides', '/guides/road-bikes', '/bikes/abc123']) {
      assert.equal(isFeedPath(path), false, path)
    }
  })

  test('rejects a path that merely starts with a feed route', () => {
    assert.equal(isFeedPath('/deals-archive'), false)
    assert.equal(isFeedPath('/deals/tomorrow'), false)
  })
})

describe('normalizePath', () => {
  test('leaves the root alone', () => {
    assert.equal(normalizePath('/'), '/')
    assert.equal(normalizePath('//'), '/')
  })

  test('strips trailing slashes', () => {
    assert.equal(normalizePath('/deals/'), '/deals')
    assert.equal(normalizePath('/deals//'), '/deals')
    assert.equal(normalizePath('/deals'), '/deals')
  })
})
