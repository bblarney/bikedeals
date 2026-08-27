// Tests for the edge renderer at functions/bikes/[id].js.
//
// Deliberately NOT inside functions/ — Cloudflare Pages turns every file under
// that directory into a route, so a test file there would ship as one.
//
// Run with `npm test` (node's built-in runner; no new dependencies).

import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { onRequestGet } = await import('../functions/bikes/[id].js')

const SHELL = `<!doctype html><html><head>
<title>BikeGrid</title>
<meta name="description" content="placeholder" />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://bikegrid.com.au/" />
<meta property="og:title" content="placeholder" />
<meta property="og:description" content="placeholder" />
<meta property="og:image" content="https://bikegrid.com.au/logo.png" />
<meta property="og:image:alt" content="BikeGrid logo" />
<meta name="twitter:title" content="placeholder" />
<meta name="twitter:description" content="placeholder" />
<meta name="twitter:image" content="https://bikegrid.com.au/logo.png" />
</head><body><div id="root"></div></body></html>`

const BIKE = {
  id: 'abc123',
  brand: 'Reid',
  model_name: 'Classic Vintage 12" Balance Bike',
  category: 'Commuter',
  frame_size: '12 inch',
  vendor_name: 'Reid Cycles',
  city: 'Brisbane',
  price_sale: 100,
  price_original: 222,
  discount_percentage: 55,
  in_stock: true,
  product_url: 'https://reidcycles.com.au/p/1',
  image_url: 'https://cdn.example.com/bike.png',
  offers: [],
}

function ctx({ status = 200, body = BIKE, fetchImpl } = {}) {
  const env = {
    ASSETS: { fetch: async () => new Response(SHELL, { status: 200 }) },
    SITE_URL: 'https://bikegrid.com.au',
    API_BASE_URL: 'https://api.test',
  }
  globalThis.fetch =
    fetchImpl ??
    (async () =>
      new Response(status === 404 ? 'not found' : JSON.stringify(body), { status }))
  return {
    request: new Request('https://bikegrid.com.au/bikes/abc123'),
    params: { id: 'abc123' },
    env,
  }
}

const textOf = (r) => r.text()

describe('bike detail edge renderer', () => {
  test('injects the real title, description and canonical', async () => {
    const res = await onRequestGet(ctx())
    const html = await textOf(res)
    assert.equal(res.status, 200)
    assert.match(html, /<title>Reid Classic Vintage 12&quot; Balance Bike 12 inch, \$100 at Reid Cycles · BikeGrid<\/title>/)
    assert.match(html, /<link rel="canonical" href="https:\/\/bikegrid\.com\.au\/bikes\/abc123" data-prerendered \/>/)
    assert.doesNotMatch(html, /content="placeholder"/)
  })

  test('a price of $100 is not expanded as a regex backreference', async () => {
    // Regression: `$1` in a String.replace replacement inserts capture group 1,
    // so "$100" spliced the whole matched <meta> tag into its own content.
    const html = await textOf(await onRequestGet(ctx()))
    const desc = html.match(/<meta name="description" content="([^"]*)"/)[1]
    assert.match(desc, /for \$100 at Reid Cycles, Brisbane/)
    assert.doesNotMatch(html, /content="[^"]*<meta/)
  })

  test('escapes quotes in scraped titles', async () => {
    const html = await textOf(await onRequestGet(ctx()))
    // The model name contains a literal " — it must not terminate the attribute.
    assert.match(html, /12&quot; Balance Bike/)
    const tags = html.match(/<meta name="description" content="[^"]*"/g)
    assert.equal(tags.length, 1, 'description attribute was terminated early')
  })

  test('cannot be broken out of via a </script> in a product title', async () => {
    const evil = { ...BIKE, model_name: '</script><script>alert(1)</script>' }
    const html = await textOf(await onRequestGet(ctx({ body: evil })))
    const block = html.match(
      /<script type="application\/ld\+json" data-prerendered>([\s\S]*?)<\/script>/,
    )
    assert.ok(block, 'JSON-LD block missing')
    assert.doesNotMatch(block[1], /<\/script>/i)
    assert.doesNotMatch(block[1], /<script/i)
    JSON.parse(block[1]) // still valid JSON
  })

  test('emits valid Product JSON-LD', async () => {
    const html = await textOf(await onRequestGet(ctx()))
    const raw = html.match(
      /<script type="application\/ld\+json" data-prerendered>([\s\S]*?)<\/script>/,
    )[1]
    const node = JSON.parse(raw)
    assert.equal(node['@type'], 'Product')
    assert.equal(node.offers.price, 100)
    assert.equal(node.offers.priceCurrency, 'AUD')
  })

  test('a missing bike is a real 404 with noindex', async () => {
    const res = await onRequestGet(ctx({ status: 404 }))
    assert.equal(res.status, 404)
    assert.match(await textOf(res), /<meta name="robots" content="noindex"/)
  })

  test('a sold-out bike still renders but is noindexed', async () => {
    const res = await onRequestGet(ctx({ body: { ...BIKE, in_stock: false } }))
    assert.equal(res.status, 200)
    const html = await textOf(res)
    assert.match(html, /<meta name="robots" content="noindex"/)
    assert.match(html, /<title>Reid Classic/)
  })

  test('an API outage fails open: the shell, 200, never a 404', async () => {
    for (const fetchImpl of [
      async () => { throw new Error('ECONNREFUSED') },
      async () => new Response('boom', { status: 500 }),
      async () => new Response('not json', { status: 200 }),
    ]) {
      const res = await onRequestGet(ctx({ fetchImpl }))
      assert.equal(res.status, 200, 'an outage must not de-index the catalogue')
      assert.match(await textOf(res), /<div id="root"><\/div>/)
    }
  })

  test('rejects a malformed id without calling the API', async () => {
    let called = false
    const c = ctx({ fetchImpl: async () => { called = true; return new Response('{}') } })
    c.params.id = '../../etc/passwd'
    const res = await onRequestGet(c)
    assert.equal(res.status, 404)
    assert.equal(called, false)
  })
})
