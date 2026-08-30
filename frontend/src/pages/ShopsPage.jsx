import { Link, useSearchParams } from 'react-router-dom'
import { canonicalFor } from '../seo'
import { useVendors } from '../hooks/useVendors'
import { formatDayLabel } from '../lib/time'
import {
  DEFAULT_SORT,
  SORTS,
  cityCounts,
  mergeShops,
  partitionByCity,
  rankShops,
  shopTotals,
  shopWhere,
} from '../lib/shops'

const CHIP_LIMIT = 8

function meta(city) {
  if (city) {
    return {
      title: `Bike Shops in ${city}: Who Is Discounting Now · BikeGrid`,
      description: `Every bike shop in ${city} we track, ranked by how much of its range is on sale right now. Updated daily from live shop inventories.`,
      canonical: canonicalFor(`/shops?city=${encodeURIComponent(city)}`),
    }
  }
  return {
    title: 'Australian Bike Shops, Ranked by Discount · BikeGrid',
    description:
      'Every Australian bike shop we track, ranked by how much of its range is marked down today. Filter by city, then open a shop to see its deals.',
    canonical: canonicalFor('/shops'),
  }
}

export default function ShopsPage() {
  const [search, setSearch] = useSearchParams()
  const city = search.get('city')
  const sort = SORTS.some((s) => s.key === search.get('sort')) ? search.get('sort') : DEFAULT_SORT

  const { data, isError } = useVendors()
  const all = data ? mergeShops(data.vendors) : null
  const chips = all ? cityCounts(all).slice(0, CHIP_LIMIT) : []
  const split = all ? partitionByCity(all, city) : null
  const local = split ? rankShops(split.local, sort) : null
  const national = split ? rankShops(split.national, sort) : null
  const totals = all ? shopTotals(city ? [...split.local, ...split.national] : all) : null

  const { title, description, canonical } = meta(city)

  // Every filter change keeps the rest of the query string, so switching sort
  // does not silently drop the city the visitor already picked.
  function setParam(key, value) {
    const next = new URLSearchParams(search)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearch(next)
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      <title>{title}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={canonical} />

      {/* Written outside the data branch on purpose: scripts/prerender.js never
          calls the API, so anything inside `if (!data)` ships as an empty page.
          Only the counts and the table wait for the request. */}
      <h1 className="text-2xl font-semibold text-slate-900 mb-2">
        {city ? `Bike shops in ${city}` : 'Who is discounting right now'}
      </h1>
      <p className="text-sm text-slate-400 mb-6 tabular-nums">
        {totals
          ? `${totals.shops} shops${city ? ` serving ${city}` : ''} · ${totals.onSale.toLocaleString()} bikes on sale · deepest cut ${totals.deepestCut}%`
          : 'Rebuilt daily from live shop inventories'}
      </p>
      <p className="text-slate-600 leading-relaxed mb-8 max-w-3xl">
        Every shop whose catalogue we read each night, ranked by how much of its range is marked
        down today. Share on sale rather than raw stock count, because counting listings just ranks
        shops by size. Open a shop to see its deals, or go straight to its own website.
      </p>

      {isError && (
        <p className="text-sm text-slate-500 mb-8">
          The shop list is unavailable right now. Please try again shortly.
        </p>
      )}

      {chips.length > 0 && (
        <nav aria-label="Filter shops by city" className="flex flex-wrap gap-2 mb-4">
          <Chip to="/shops" active={!city} label="All shops" count={all.length} />
          {chips.map((c) => (
            <Chip
              key={c.city}
              to={`/shops?city=${encodeURIComponent(c.city)}${sort !== DEFAULT_SORT ? `&sort=${sort}` : ''}`}
              active={city === c.city}
              label={c.city}
              count={c.shops}
            />
          ))}
        </nav>
      )}

      {all && (
        <div className="flex flex-wrap items-center gap-2 pt-4 mb-6 border-t border-slate-200">
          <span className="text-xs text-slate-400 mr-1">Sort by</span>
          {SORTS.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setParam('sort', s.key === DEFAULT_SORT ? null : s.key)}
              aria-pressed={sort === s.key}
              className={`text-sm rounded-full px-3 py-1 border transition-colors ${
                sort === s.key
                  ? 'bg-slate-900 border-slate-900 text-white font-semibold'
                  : 'bg-white border-slate-200 text-slate-600 hover:border-orange-400 hover:text-orange-600'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      {local && local.length > 0 && (
        <section className="mb-10">
          {city && (
            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Shops with a {city} storefront{' '}
              <span className="text-slate-400 font-normal normal-case tracking-normal tabular-nums">
                {local.length}
              </span>
            </h2>
          )}
          <ShopTable rows={local} />
        </section>
      )}

      {national && national.length > 0 && (
        <section className="mb-10">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            {city ? `Also delivers to ${city}` : 'Chains and online sellers'}{' '}
            <span className="text-slate-400 font-normal normal-case tracking-normal tabular-nums">
              {national.length}
            </span>
          </h2>
          {city && (
            <p className="text-sm text-slate-500 mb-3">
              Buy from these national chains in {city}.
            </p>
          )}
          <ShopTable rows={national} />
        </section>
      )}

      {all && local.length === 0 && national.length === 0 && (
        <p className="text-slate-600">
          No shop in {city} has stock in the feed today.{' '}
          <Link to="/shops" className="text-orange-600 hover:text-orange-700">
            See every shop
          </Link>
          .
        </p>
      )}

      <p className="text-xs text-slate-400 mt-8 max-w-3xl leading-relaxed">
        A chain's storefronts count once, not once per city, so these totals match what the feed
        returns. Shops with nothing discounted today are still listed: a shop is not missing from
        this page because it happens to be at full price.
      </p>
    </div>
  )
}

function Chip({ to, active, label, count }) {
  return (
    <Link
      to={to}
      aria-current={active ? 'page' : undefined}
      className={`inline-flex items-center gap-2 text-sm rounded-lg px-3 py-1.5 border transition-colors ${
        active
          ? 'bg-orange-600 border-orange-600 text-white font-semibold'
          : 'bg-white border-slate-200 text-slate-700 hover:border-orange-400 hover:text-orange-600'
      }`}
    >
      {label}
      <span className={`text-xs tabular-nums ${active ? 'text-orange-100' : 'text-slate-400'}`}>
        {count}
      </span>
    </Link>
  )
}

// A list of links rather than a <table>: every row is one navigation target, and
// a table whose every cell sits inside an anchor announces far worse than this
// does. The columns are visual, and they collapse on a phone.
function ShopTable({ rows }) {
  return (
    <>
      <div className="hidden md:flex items-center gap-4 px-4 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        <span className="flex-1">Shop</span>
        <span className="w-16 text-right">Listings</span>
        <span className="w-16 text-right">On sale</span>
        <span className="w-28 text-right">Share</span>
        <span className="w-20 text-right">Deepest</span>
        <span className="hidden lg:inline w-20 text-right">Checked</span>
        <span className="w-4" aria-hidden="true" />
      </div>
      <ul className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100 overflow-hidden">
        {rows.map((row, i) => (
          <li key={row.slug}>
            <Link
              to={row.path}
              className="group flex items-center gap-4 px-4 py-3 hover:bg-orange-50 transition-colors"
            >
              <span className="md:hidden w-5 text-xs font-bold text-slate-300 tabular-nums flex-shrink-0">
                {i + 1}
              </span>
              <span className="flex-1 min-w-0">
                <span className="block text-sm font-semibold text-slate-900 group-hover:text-orange-700 truncate">
                  {row.name}
                </span>
                <span className="block text-xs text-slate-400 tabular-nums truncate">
                  <span className="md:hidden">
                    {row.listings} listings · {row.onSale} on sale
                  </span>
                  <span className="hidden md:inline">{shopWhere(row)}</span>
                </span>
              </span>
              <span className="hidden md:block w-16 text-right text-sm text-slate-600 tabular-nums">
                {row.listings}
              </span>
              <span className="hidden md:block w-16 text-right text-sm tabular-nums text-slate-600">
                {row.onSale || <span className="text-slate-300">0</span>}
              </span>
              <span className="w-16 md:w-28 flex items-center justify-end gap-2 text-sm tabular-nums text-slate-700">
                <span className="hidden md:block w-14 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                  <span
                    className="block h-full bg-orange-400 group-hover:bg-orange-500"
                    style={{ width: `${row.share}%` }}
                  />
                </span>
                <span className={row.share ? '' : 'text-slate-300'}>{row.share}%</span>
              </span>
              <span className="hidden md:block w-20 text-right text-sm tabular-nums font-semibold text-emerald-700">
                {row.deepestCut ? `${row.deepestCut}%` : <span className="text-slate-300 font-normal">none</span>}
              </span>
              <span className="hidden lg:block w-20 text-right text-xs text-slate-400">
                {row.lastSuccessAt ? formatDayLabel(new Date(row.lastSuccessAt)) : '–'}
              </span>
              <svg
                width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
                className="w-4 flex-shrink-0 text-slate-300 group-hover:text-orange-600"
              >
                <path d="m9 18 6-6-6-6" />
              </svg>
            </Link>
          </li>
        ))}
      </ul>
    </>
  )
}
