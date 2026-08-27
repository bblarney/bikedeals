import { buildBikeMetaFor, buildBikeJsonLdFor, serializeJsonLd } from './lib/bikeMeta.js'
import { categoryPath } from './content/categories.js'

export { serializeJsonLd }

const FALLBACK = 'https://bikegrid.com.au'

// The site origin, without a trailing slash. lib/bikeMeta.js cannot read
// import.meta.env (it also runs in the Workers runtime), so it is passed in.
function siteOrigin() {
  return (import.meta.env.VITE_PUBLIC_URL || FALLBACK).replace(/\/$/, '')
}

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

// Title, description and canonical for a feed URL. The canonical is built from
// the category route rather than a query string, so /gravel-bikes and
// /deals?category=Gravel cannot both claim to be the page.
export function buildPageMeta(params) {
  const category = params.category?.[0]
  const city = params.city?.length === 1 ? params.city[0] : null
  const catLabel = category ? (CATEGORY_LABELS[category] ?? category) : null
  const base = category ? categoryPath(category) : '/deals'
  const canonical = canonicalFor(city ? `${base}?city=${encodeURIComponent(city)}` : base)

  if (catLabel && city) {
    return {
      title: `${catLabel} on Sale in ${city} · BikeGrid`,
      description: `Find discounted ${catLabel.toLowerCase()} from local bike shops in ${city}. Updated daily.`,
      canonical,
    }
  }
  if (catLabel) {
    return {
      title: `${catLabel} on Sale · BikeGrid Australia`,
      description: `Find discounted ${catLabel.toLowerCase()} from local Australian bike shops. Updated daily.`,
      canonical,
    }
  }
  if (city) {
    return {
      title: `Bike Deals in ${city} · BikeGrid`,
      description: `Browse discounted bikes from local bike shops in ${city}. Updated daily.`,
      canonical,
    }
  }
  return {
    title: 'Bikes on Sale at Australian Shops · BikeGrid',
    description: 'Discounted bikes from local Australian bike shops, in one feed. Filter by category, size, city, brand, frame material and groupset.',
    canonical,
  }
}

// Both delegate to lib/bikeMeta.js, which the edge renderer at
// functions/bikes/[id].js imports too — one implementation, so the
// pre-JS <head> and the client-rendered one cannot disagree.
export function buildBikeMeta(bike) {
  return buildBikeMetaFor(bike, siteOrigin())
}

export function buildBikeJsonLd(bike) {
  return buildBikeJsonLdFor(bike, siteOrigin())
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
