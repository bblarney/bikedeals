// The shops tab's arithmetic, kept out of the components so it can be tested
// with the bare node runner. Only imports content/shops.js, which is generated
// and dependency-free. See test/shops.test.js.

import { SHOPS, isNational, servesCity } from '../content/shops.js'

// The API returns counts keyed on vendor_name; the registry holds the slug, the
// cities and the shop's own URL. Joining them here is what lets the API stay
// out of the YAML.
//
// A vendor with stock but no registry entry is dropped. That happens only for a
// shop retired from scrapers/vendors/ whose rows have not yet fallen out of the
// feed, and it has no slug, so there is no page to link it to.
export function mergeShops(vendors = []) {
  const byName = new Map(SHOPS.map((s) => [s.name, s]))
  return vendors.flatMap((v) => {
    const shop = byName.get(v.vendor_name)
    if (!shop) return []
    return [{
      ...shop,
      listings: v.listings ?? 0,
      onSale: v.on_sale ?? 0,
      deepestCut: v.deepest_cut ?? 0,
      share: v.listings ? Math.round((v.on_sale / v.listings) * 100) : 0,
      lastSuccessAt: v.last_success_at ?? null,
      national: isNational(shop),
    }]
  })
}

export const SORTS = [
  { key: 'share', label: 'Share on sale' },
  { key: 'deepest', label: 'Deepest cut' },
  { key: 'listings', label: 'Most listings' },
  { key: 'name', label: 'Name' },
]

export const DEFAULT_SORT = 'share'

// Ranked, with a total order. Every comparison falls through to the name, so
// the table cannot reshuffle between renders when two shops tie: on a page whose
// rows are links, a row that moves under the cursor is a misclick.
export function rankShops(rows, sort = DEFAULT_SORT) {
  const byName = (a, b) => a.name.localeCompare(b.name)
  const cmp = {
    // Share first, then the absolute count: 4 of 4 is a real 100%, but it
    // should not outrank 462 of 468 on a page about where the deals are.
    share: (a, b) => b.share - a.share || b.onSale - a.onSale || byName(a, b),
    deepest: (a, b) => b.deepestCut - a.deepestCut || b.share - a.share || byName(a, b),
    listings: (a, b) => b.listings - a.listings || byName(a, b),
    name: byName,
  }[sort] ?? byName
  return [...rows].sort(cmp)
}

// Split a city's shops into the ones you can walk into and the ones that post
// it to you.
//
// This is not presentation fussiness. A chain stores one catalogue row per city,
// so filtering the feed to Melbourne leaves 99 Bikes' listing count exactly
// where it was: 468 nationally and 468 "in Melbourne". Ranking the two kinds in
// one table would put a national catalogue above every local shop on a number
// that is not a Melbourne number. See the note in api/main.py get_vendors.
export function partitionByCity(rows, city) {
  const inCity = city ? rows.filter((r) => servesCity(r, city)) : rows
  return {
    local: inCity.filter((r) => !r.national),
    national: inCity.filter((r) => r.national),
  }
}

// Cities that actually have a shop with stock, most shops first. Drives the
// filter chips, so the number has to be what the chip then shows you.
//
// The ships-anywhere shops are added to every city, because servesCity puts
// them in every city's results. Counting only the shops that name the city
// undercounted each chip by exactly the online sellers, so a Melbourne chip
// reading 22 opened a page headed "23 shops serving Melbourne".
export function cityCounts(rows) {
  const counts = new Map()
  let anywhere = 0
  for (const row of rows) {
    if (row.cities.length === 0) {
      anywhere += 1
      continue
    }
    for (const city of row.cities) {
      counts.set(city, (counts.get(city) ?? 0) + 1)
    }
  }
  return [...counts.entries()]
    .map(([city, shops]) => ({ city, shops: shops + anywhere }))
    .sort((a, b) => b.shops - a.shops || a.city.localeCompare(b.city))
}

// A shop's place in its own city's local ranking, for the shop page's
// "2nd of 17" line. Null for a chain, which is not in that ranking at all.
export function rankInCity(rows, shop, sort = DEFAULT_SORT) {
  if (!shop || shop.national) return null
  const city = shop.cities[0]
  if (!city) return null
  const { local } = partitionByCity(rows, city)
  const ranked = rankShops(local, sort)
  const index = ranked.findIndex((r) => r.slug === shop.slug)
  return index < 0 ? null : { position: index + 1, total: ranked.length, city }
}

const ORDINALS = ['th', 'st', 'nd', 'rd']

export function ordinal(n) {
  const rem100 = n % 100
  const rem10 = n % 10
  return `${n}${rem100 >= 11 && rem100 <= 13 ? 'th' : (ORDINALS[rem10] ?? 'th')}`
}

// Totals for the page subline. Listings sum cleanly across shops because the
// API already collapsed each shop's chain storefronts and size variants.
export function shopTotals(rows) {
  return {
    shops: rows.length,
    listings: rows.reduce((n, r) => n + r.listings, 0),
    onSale: rows.reduce((n, r) => n + r.onSale, 0),
    deepestCut: rows.reduce((n, r) => Math.max(n, r.deepestCut), 0),
  }
}

// What to say under a shop's name. A chain's spread is the point: a big listing
// count next to one suburb would read as one enormous shopfront.
export function shopWhere(shop) {
  if (shop.cities.length === 0) return 'Ships anywhere'
  if (shop.cities.length === 1) return shop.cities[0]
  return `${shop.cities.length} cities`
}
