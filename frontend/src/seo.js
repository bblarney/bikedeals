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
