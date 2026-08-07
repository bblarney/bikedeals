import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import BikeCard from './BikeCard'

// A strip of real deals for a guide section, plus the link into the filtered
// feed. Two things here are load-bearing and easy to lose in a refactor:
//
// 1. The CTA renders unconditionally, outside the query result. The build-time
//    prerender never fetches (see scripts/prerender.js), so the cards below are
//    invisible to crawlers — permanently, by design. This <Link> is the part
//    that ends up in the static HTML, so it is the actual internal link, not
//    decoration. It also means an empty rail still reads as a finished section.
//
// 2. Results are deduped by brand+model. Every size and every store of the same
//    bike is its own row, so an undeduped top-4 on a narrow query renders four
//    copies of one bike — ?category=E-Bike&q=cargo returns eight identical Cube
//    trikes in its first nine rows. Overfetch, dedupe, then slice.
//
// Pins arrive as props rather than from usePins(), the same way RelatedBikes
// takes them. A page has several rails, and usePins keeps its state in a
// component-local useState that it writes back to localStorage wholesale — one
// hook call per rail would give each rail its own divergent copy, so saving in
// one rail and then another would drop the first save.
const FETCH_LIMIT = 48

// Some shops list accessories under a bike category, so a keyword rail can pick
// up a $28 "Padded rear Seat - E-Cargo Bike" and show it as a cargo bike. There
// is a wide gap between accessory prices (all under ~$150) and the cheapest
// complete bike (~$500), so a floor here separates them cleanly. Override via
// the minPrice prop if a rail ever needs to go lower.
const MIN_PRICE = 200

// Written out in full: Tailwind scans source for complete class names, so an
// interpolated `sm:grid-cols-${n}` would never be generated.
const GRID_COLS = {
  2: 'grid-cols-2 gap-4 mt-3',
  3: 'grid-cols-2 sm:grid-cols-3 gap-4 mt-3',
  4: 'grid-cols-2 sm:grid-cols-4 gap-4 mt-3',
}

export default function CatalogRail({
  title,
  params,
  ctaLabel,
  ctaTo,
  count = 4,
  note,
  minPrice = MIN_PRICE,
  pinnedIds = new Set(),
  onTogglePin = () => {},
}) {
  const query = { min_price: minPrice, ...params, limit: FETCH_LIMIT, sort: 'discount_desc' }
  const { data } = useQuery({
    queryKey: ['catalog-rail', query, count],
    queryFn: () => api.getBikes(query),
    staleTime: 5 * 60 * 1000,
  })

  const seen = new Set()
  const bikes = []
  for (const bike of data?.results ?? []) {
    const key = `${bike.brand}|${bike.model_name}`.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    bikes.push(bike)
    if (bikes.length === count) break
  }

  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between gap-4 mb-1">
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        <Link to={ctaTo} className="text-sm text-orange-600 hover:underline whitespace-nowrap">
          {ctaLabel} →
        </Link>
      </div>
      {note && <p className="text-xs text-slate-400 mb-3">{note}</p>}
      {bikes.length > 0 && (
        <div className={`grid ${GRID_COLS[count] ?? GRID_COLS[4]}`}>
          {bikes.map((bike) => (
            <BikeCard
              key={bike.id}
              bike={bike}
              isPinned={pinnedIds.has(bike.id)}
              onTogglePin={onTogglePin}
            />
          ))}
        </div>
      )}
    </section>
  )
}
