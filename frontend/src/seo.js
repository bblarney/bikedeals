const FALLBACK = 'https://bikegrid.com.au'

export function canonicalFor(path = '/') {
  const base = import.meta.env.VITE_PUBLIC_URL || FALLBACK
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${base.replace(/\/$/, '')}${normalized}`
}

const CATEGORY_LABELS = {
  Road: 'Road Bikes',
  Mountain: 'Mountain Bikes',
  Gravel: 'Gravel Bikes',
  'E-Bike': 'E-Bikes',
  Commuter: 'Commuter Bikes',
}

export function buildPageMeta(params) {
  const category = params.category?.[0]
  const city = params.city?.length === 1 ? params.city[0] : null
  const catLabel = category ? (CATEGORY_LABELS[category] ?? category) : null

  if (catLabel && city) {
    const qs = `?category=${encodeURIComponent(category)}&city=${encodeURIComponent(city)}`
    return {
      title: `${catLabel} on Sale in ${city} · BikeGrid`,
      description: `Find discounted ${catLabel.toLowerCase()} from local bike shops in ${city}. Updated daily.`,
      canonical: canonicalFor(`/${qs}`),
    }
  }
  if (catLabel) {
    return {
      title: `${catLabel} on Sale · BikeGrid Australia`,
      description: `Find discounted ${catLabel.toLowerCase()} from local Australian bike shops. Updated daily.`,
      canonical: canonicalFor(`/?category=${encodeURIComponent(category)}`),
    }
  }
  if (city) {
    return {
      title: `Bike Deals in ${city} · BikeGrid`,
      description: `Browse discounted bikes from local bike shops in ${city}. Updated daily.`,
      canonical: canonicalFor(`/?city=${encodeURIComponent(city)}`),
    }
  }
  return {
    title: 'BikeGrid — Daily Bike Deals from Australian Shops',
    description: 'Browse hundreds of discounted bikes from local Australian bike shops. Updated daily. Filter by category, size, and brand.',
    canonical: canonicalFor('/'),
  }
}

export function buildBikeMeta(bike) {
  const name = `${bike.brand} ${bike.model_name}`.trim()
  const size = bike.frame_size ? ` ${bike.frame_size}` : ''
  const price = Math.round(bike.price_sale)
  const where = [bike.vendor_name, bike.city].filter(Boolean).join(', ')
  const off = bike.discount_percentage > 0 ? `${bike.discount_percentage}% off — ` : ''
  return {
    title: `${name}${size} — $${price} at ${bike.vendor_name} · BikeGrid`,
    description: `${off}${name}${size} for $${price}${where ? ` at ${where}` : ''}. Compare prices across local Australian bike shops on BikeGrid.`,
    canonical: canonicalFor(`/bikes/${bike.id}`),
  }
}

// Schema.org BreadcrumbList. Takes [{ name, path }] in trail order.
export function buildBreadcrumbJsonLd(items) {
  return {
    '@context': 'https://schema.org/',
    '@type': 'BreadcrumbList',
    itemListElement: items.map(({ name, path }, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name,
      item: canonicalFor(path),
    })),
  }
}

// Schema.org Product + AggregateOffer for rich Google results. Built from the
// detail endpoint's cross-shop `offers` list.
export function buildBikeJsonLd(bike) {
  const offers = bike.offers ?? []
  const prices = offers.map((o) => o.price_sale)
  const node = {
    '@context': 'https://schema.org/',
    '@type': 'Product',
    name: `${bike.brand} ${bike.model_name}`.trim(),
    brand: { '@type': 'Brand', name: bike.brand },
    category: bike.category,
    url: canonicalFor(`/bikes/${bike.id}`),
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
