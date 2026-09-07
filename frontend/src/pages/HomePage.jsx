import { useMemo, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { CATEGORIES, categoryPath } from '../content/categories'
import { GUIDES } from '../content/guides'
import { REGIONS, sortSizes } from '../constants'
import { REGION_KEY } from '../lib/landing'
import { pick } from '../lib/market'
import { homeDealsParams } from '../lib/queries'
import { formatDayLabel } from '../lib/time'
import { canonicalFor } from '../seo'
import { useBikes } from '../hooks/useBikes'
import { useFilters } from '../hooks/useFilters'
import { useMarket } from '../hooks/useMarket'
import { useStats } from '../hooks/useStats'
import { usePins } from '../hooks/usePins'
import BikeCard from '../components/BikeCard'
import FlagAU from '../components/FlagAU'

// Everything the feed understands. `/` used to be the feed, so anything indexed
// or linked with one of these still arrives here and has to be forwarded rather
// than silently dropped onto a marketing page.
const FEED_PARAMS = [
  'category', 'city', 'size', 'vendor', 'brand', 'frame_material',
  'drivetrain_groupset', 'min_discount', 'min_price', 'max_price', 'q',
  'added_since', 'sort', 'offset', 'sku', 'product_key',
]

function legacyFeedRedirect(search) {
  if (!FEED_PARAMS.some((k) => search.has(k))) return null
  const next = new URLSearchParams(search)
  const category = next.get('category')
  // One category becomes the route; two or more stay query parameters, because
  // /road-bikes cannot also mean gravel.
  if (category && next.getAll('category').length === 1) {
    next.delete('category')
    return `${categoryPath(category)}${next.toString() ? `?${next}` : ''}`
  }
  return `/deals${next.toString() ? `?${next}` : ''}`
}

const HOME_GUIDES = ['road-bikes', 'gravel-bikes', 'electric-bikes']

// Share of a chart's rows held by one series, as a whole percent.
function shareOf(points, chart, series) {
  const rows = pick(points, chart)
  const total = rows.reduce((a, p) => a + p.n, 0)
  if (!total) return null
  const mine = rows.filter((p) => p.series === series).reduce((a, p) => a + p.n, 0)
  return Math.round((mine / total) * 100)
}

function marketFigures(data) {
  if (!data) return null
  const { points, total_listings: total } = data
  const onSale = pick(points, 'discount_hist').reduce((a, p) => a + p.n, 0)

  const byCategory = {}
  for (const p of pick(points, 'cell_totals')) {
    byCategory[p.series] = (byCategory[p.series] ?? 0) + p.n
  }

  return {
    total,
    onSale,
    byCategory,
    shimano: shareOf(points, 'groupset_brand_by_category', 'Shimano'),
    carbon: shareOf(points, 'material_by_band', 'Carbon'),
    onSaleShare: total ? Math.round((onSale / total) * 100) : null,
  }
}

// The finder's selects sit inside one white pill, so they carry no border or
// box of their own: the pill is the control.
const finderSelect =
  'w-full bg-white text-slate-900 text-sm font-medium py-0.5 cursor-pointer appearance-none focus:outline-none focus:ring-2 focus:ring-orange-500 rounded'

export default function HomePage() {
  const [search] = useSearchParams()
  const redirect = legacyFeedRedirect(search)

  const { data: stats } = useStats()
  const { data: filters } = useFilters({})
  const { data: market } = useMarket()
  const { data: deals } = useBikes(homeDealsParams())
  const { pinnedIds, togglePin } = usePins()

  const figures = useMemo(() => marketFigures(market), [market])

  const sizes = useMemo(() => (filters?.sizes ? sortSizes(filters.sizes) : []), [filters])

  if (redirect) return <Navigate to={redirect} replace />

  const total = filters?.total_bikes ?? figures?.total ?? null

  return (
    <>
      <title>Bike Deals from Local Australian Shops · BikeGrid</title>
      <meta
        name="description"
        content="We check local Australian bike shops every day and list the bikes they have marked down. Filter by category, size, city, brand, frame material and groupset."
      />
      <link rel="canonical" href={canonicalFor('/')} />

      <Hero
        total={total}
        onSale={figures?.onSale}
        newToday={stats?.new_today}
        shops={stats?.shops_tracked}
        lastScrapedAt={filters?.last_scraped_at}
        categories={filters?.categories ?? []}
        sizes={sizes}
        cities={filters?.cities ?? []}
      />

      <CategoryTiles counts={figures?.byCategory} />

      <section className="max-w-7xl mx-auto px-4 sm:px-6 pb-8">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
            Today's deepest discounts
          </h2>
          <Link to="/deals?min_discount=25" className="text-sm font-bold text-orange-600 hover:text-orange-700">
            {figures?.onSale ? `See all ${figures.onSale.toLocaleString()} on sale` : 'See everything on sale'} &rsaquo;
          </Link>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {(deals?.results ?? []).map((bike) => (
            <BikeCard
              key={bike.id}
              bike={bike}
              isPinned={pinnedIds.has(bike.id)}
              onTogglePin={togglePin}
            />
          ))}
          {!deals && Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-100 aspect-[4/5] animate-pulse" />
          ))}
        </div>
      </section>

      <GuideBand />
      <MarketStrip figures={figures} />
    </>
  )
}

function Hero({ total, onSale, newToday, shops, lastScrapedAt, categories, sizes, cities }) {
  const [category, setCategory] = useState('')
  const [size, setSize] = useState('')
  const [city, setCity] = useState('')

  function search() {
    const qs = new URLSearchParams()
    if (size) qs.set('size', size)
    if (city) {
      qs.set('city', city)
      const region = REGIONS.find((r) => r.cities.includes(city))
      try {
        localStorage.setItem(REGION_KEY, region ? region.name : '__all__')
      } catch {
        // Storage blocked. The filter still applies for this visit.
      }
    }
    const suffix = qs.toString() ? `?${qs}` : ''
    return category ? categoryPath(category, suffix) : `/deals${suffix}`
  }

  const updated = lastScrapedAt ? formatDayLabel(new Date(lastScrapedAt)) : null

  return (
    <section className="bg-navy-900 text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="flex items-center gap-2.5 mb-6">
          <FlagAU className="h-4 w-8 rounded-sm ring-1 ring-white/20" />
          <span className="text-xs tabular-nums uppercase tracking-[0.16em] text-slate-400">
            Australia wide
          </span>
        </div>

        <h1 className="font-display text-4xl sm:text-5xl lg:text-[3.4rem] font-extrabold tracking-tight leading-[1.03] max-w-[17ch]">
          Discounted bikes from local Australian shops, <span className="text-orange-400">in one place.</span>
        </h1>

        <p className="mt-4 text-slate-300 max-w-[54ch]">
          We check {shops ? `${shops} local shops` : 'local bike shops around the country'} every day
          {onSale ? `. ${onSale.toLocaleString()} bikes are marked down right now` : ''}
          {newToday ? `, and ${newToday} of them went on sale since yesterday` : ''}.
        </p>

        <div className="mt-7 bg-white rounded-2xl p-2 flex flex-col sm:flex-row gap-2 sm:items-center max-w-3xl shadow-xl shadow-navy-900/40">
          <Field label="Looking for" value={category} onChange={setCategory} options={categories} anyLabel="Any bike" />
          <Field label="Size" value={size} onChange={setSize} options={sizes} anyLabel="Any size" />
          <Field label="Near" value={city} onChange={setCity} options={cities} anyLabel="Anywhere" last />
          <Link
            to={search()}
            className="bg-orange-600 hover:bg-orange-700 text-white font-bold rounded-xl px-6 py-3 text-center transition-colors flex-shrink-0"
          >
            Show deals
          </Link>
        </div>

        <div className="mt-7 flex flex-wrap items-center gap-x-8 gap-y-4 text-sm text-slate-400">
          <Stat value={total ? total.toLocaleString() : '…'} label="bikes tracked" />
          <Stat value={shops ?? '…'} label="shops" />
          <Stat value={updated ?? '…'} label="last updated" />
          <Link
            to="/deals"
            className="sm:ml-auto text-orange-400 hover:text-orange-300 font-bold transition-colors"
          >
            Or browse {total ? total.toLocaleString() : 'everything'} with full filters &rsaquo;
          </Link>
        </div>
      </div>
    </section>
  )
}

function Field({ label, value, onChange, options, anyLabel, last = false }) {
  return (
    <label className={`flex-1 min-w-0 px-3 py-1.5 ${last ? '' : 'sm:border-r sm:border-slate-100'}`}>
      <span className="block text-[10px] tabular-nums uppercase tracking-[0.11em] text-slate-500">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={finderSelect}>
        <option value="">{anyLabel}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  )
}

function Stat({ value, label }) {
  return (
    <span className="flex items-baseline gap-2">
      <b className="tabular-nums text-lg font-semibold text-white tracking-tight">{value}</b>
      {label}
    </span>
  )
}

function CategoryTiles({ counts }) {
  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {CATEGORIES.map((c) => (
          <Link
            key={c.path}
            to={c.path}
            className="group border border-slate-200 rounded-xl p-4 hover:border-orange-400 hover:shadow-md transition-all duration-150 bg-white"
          >
            <p className="font-bold text-slate-900 group-hover:text-orange-600 transition-colors">{c.label}</p>
            <p className="text-xs text-slate-500 mt-0.5">
              {counts?.[c.category] ? `${counts[c.category].toLocaleString()} bikes` : c.blurb}
            </p>
            <svg className="mt-3 ml-auto block text-slate-200 group-hover:text-orange-300 transition-colors" width="44" height="28" viewBox="0 0 64 40" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="14" cy="28" r="10" /><circle cx="50" cy="28" r="10" />
              <path d="M14 28 27 12h16M27 12l5 16M32 28 43 12M32 28h18M24 11h7M40 9h7" />
            </svg>
          </Link>
        ))}
      </div>
    </section>
  )
}

function GuideBand() {
  const shown = HOME_GUIDES.map((slug) => GUIDES.find((g) => g.slug === slug)).filter(Boolean)
  return (
    <section className="bg-slate-100 border-y border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
        <div className="flex items-baseline justify-between mb-5">
          <h2 className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
            Not sure which bike you need?
          </h2>
          <Link to="/guides" className="text-sm font-bold text-orange-600 hover:text-orange-700">
            All five guides &rsaquo;
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {shown.map((g) => (
            <Link
              key={g.path}
              to={g.path}
              className="group bg-white rounded-xl p-5 flex flex-col gap-2 hover:shadow-md transition-shadow"
            >
              <p className="font-display text-lg font-bold tracking-tight text-slate-900 group-hover:text-orange-600 transition-colors">
                {g.label}
              </p>
              <p className="text-sm text-slate-600 leading-relaxed">{g.cardBlurb}</p>
              <p className="text-sm font-bold text-orange-600 mt-auto pt-2">Read the guide &rsaquo;</p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}

function MarketStrip({ figures }) {
  return (
    <section className="bg-slate-900 text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 flex flex-col lg:flex-row lg:items-center gap-6 lg:gap-12">
        <h2 className="font-display text-xl sm:text-2xl font-extrabold tracking-tight max-w-[15ch]">
          What the market looks like this morning
        </h2>
        <dl className="flex flex-wrap gap-8">
          <Figure value={figures?.shimano} suffix="%" label="of named groupsets are Shimano" />
          <Figure value={figures?.carbon} suffix="%" label="of known frames are carbon" />
          <Figure value={figures?.onSaleShare} suffix="%" label="of everything we track is on sale" />
        </dl>
        <Link
          to="/trends"
          className="lg:ml-auto flex-shrink-0 bg-orange-600 hover:bg-orange-700 text-white font-bold rounded-full px-5 py-2.5 text-sm transition-colors"
        >
          Read the market report
        </Link>
      </div>
    </section>
  )
}

function Figure({ value, suffix, label }) {
  return (
    <div>
      <dt className="sr-only">{label}</dt>
      <dd>
        <b className="block tabular-nums text-2xl font-semibold tracking-tight">
          {value == null ? '…' : `${value}${suffix}`}
        </b>
        <span className="text-xs text-slate-400 max-w-[22ch] block">{label}</span>
      </dd>
    </div>
  )
}
