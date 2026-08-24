// Metadata and structured data for a bike detail page.
//
// This module is loaded from TWO runtimes: the React app (via seo.js) and the
// Cloudflare Pages Function at functions/bikes/[id].js, which renders the same
// page's <head> at the edge before any JavaScript runs. Both must produce
// identical output — a server-rendered canonical or JSON-LD that disagrees with
// the client-rendered one is worse than none at all.
//
// It therefore carries the same constraint as content/guides.js and
// lib/landing.js: **no JSX, no imports, and no `import.meta.env`.** The site
// origin is passed in rather than read from the environment, because the
// Workers runtime has no `import.meta.env` to read.

export function bikePath(bike) {
  return `/bikes/${bike.id}`
}

export function buildBikeMetaFor(bike, siteUrl) {
  const name = `${bike.brand} ${bike.model_name}`.trim()
  const size = bike.frame_size ? ` ${bike.frame_size}` : ''
  const price = Math.round(bike.price_sale)
  const where = [bike.vendor_name, bike.city].filter(Boolean).join(', ')
  const off = bike.discount_percentage > 0 ? `${bike.discount_percentage}% off — ` : ''
  return {
    title: `${name}${size} — $${price} at ${bike.vendor_name} · BikeGrid`,
    description: `${off}${name}${size} for $${price}${where ? ` at ${where}` : ''}. Compare prices across local Australian bike shops on BikeGrid.`,
    canonical: `${String(siteUrl).replace(/\/$/, '')}${bikePath(bike)}`,
  }
}

// Schema.org Product + AggregateOffer for rich Google results. Built from the
// detail endpoint's cross-shop `offers` list, which is grouped on product_key —
// see docs/data-model.md. Grouping on the raw SKU used to put an unrelated
// bike's price into lowPrice, which is exactly the number Google surfaces.
export function buildBikeJsonLdFor(bike, siteUrl) {
  const offers = bike.offers ?? []
  const prices = offers.map((o) => o.price_sale)
  const node = {
    '@context': 'https://schema.org/',
    '@type': 'Product',
    name: `${bike.brand} ${bike.model_name}`.trim(),
    brand: { '@type': 'Brand', name: bike.brand },
    category: bike.category,
    url: `${String(siteUrl).replace(/\/$/, '')}${bikePath(bike)}`,
  }
  if (bike.image_url) node.image = bike.image_url
  if (offers.length >= 2) {
    node.offers = {
      '@type': 'AggregateOffer',
      priceCurrency: 'AUD',
      lowPrice: Math.min(...prices),
      highPrice: Math.max(...prices),
      offerCount: offers.length,
      availability: 'https://schema.org/InStock',
    }
  } else {
    node.offers = {
      '@type': 'Offer',
      priceCurrency: 'AUD',
      price: bike.price_sale,
      availability: bike.in_stock
        ? 'https://schema.org/InStock'
        : 'https://schema.org/OutOfStock',
      url: bike.product_url,
    }
  }
  return node
}

// JSON destined for a <script> block, with the characters that can terminate it
// neutralised.
//
// JSON.stringify does NOT escape `<`, and every string in these nodes is scraped
// third-party text: a shop product title containing `</script><script>…` would
// otherwise close the JSON-LD block and execute. U+2028/U+2029 are escaped too —
// they are valid in JSON but are line terminators in JavaScript.
export function serializeJsonLd(node) {
  return JSON.stringify(node)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029')
}
