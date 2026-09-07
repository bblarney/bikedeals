import { Link, useParams } from 'react-router-dom'
import { canonicalFor, buildBreadcrumbJsonLd, serializeJsonLd } from '../seo'
import { shopBySlug } from '../content/shops'
import { useVendors } from '../hooks/useVendors'
import { useFilters } from '../hooks/useFilters'
import { useBikes } from '../hooks/useBikes'
import BikeCard from '../components/BikeCard'
import { money } from '../lib/money'
import { formatDayLabel } from '../lib/time'
import { mergeShops, rankInCity, ordinal, shopWhere } from '../lib/shops'
import { shopDealsParams, shopFacetParams } from '../lib/queries'

// The slug is resolved here and the shop is handed to a child, so the hooks
// below it never run for a URL that names no shop. Guarding inside one
// component would mean either conditional hooks or firing three requests to
// render a 404.
export default function ShopDetailPage() {
  const { slug } = useParams()
  const shop = shopBySlug(slug)
  return shop ? <ShopDetail shop={shop} /> : <ShopNotFound />
}

function ShopNotFound() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <title>Shop not found · BikeGrid</title>
      <meta name="robots" content="noindex" />
      <h1 className="text-2xl font-semibold text-slate-900 mb-3">We don't track that shop</h1>
      <p className="text-slate-600 mb-6">
        It may have closed, or we may never have read its catalogue.
      </p>
      <Link to="/shops" className="text-orange-600 hover:text-orange-700 font-medium">
        See every shop we track →
      </Link>
    </div>
  )
}

function ShopDetail({ shop }) {
  // Name, cities and outbound link come from the generated registry copy. The
  // numbers come from the API: at build time scripts/prerender.js seeds these
  // three queries (keyed by lib/queries.js, so they match), and in the browser
  // they refetch; either way the empty shape below is what a cold build ships.
  const { data: vendorData } = useVendors()
  const rows = vendorData ? mergeShops(vendorData.vendors) : null
  const row = rows ? rows.find((r) => r.slug === shop.slug) : null
  const rank = row ? rankInCity(rows, row) : null

  // The vendor-scoped facets already carry this shop's price range and the
  // categories it stocks, so neither needs an endpoint of its own.
  const { data: facets } = useFilters(shopFacetParams(shop.name))
  const { data: deals } = useBikes(shopDealsParams(shop.name))

  const homeCity = shop.cities.length === 1 ? shop.cities[0] : null
  const backTo = homeCity ? `/shops?city=${encodeURIComponent(homeCity)}` : '/shops'
  const priceRange = facets?.price_range
  const categories = facets?.categories ?? []

  const trail = [
    { name: 'Deals', path: '/' },
    { name: 'Shops', path: '/shops' },
    ...(homeCity ? [{ name: homeCity, path: backTo }] : []),
    { name: shop.name, path: shop.path },
  ]

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      <title>{`${shop.name} Bike Deals${homeCity ? `, ${homeCity}` : ''} · BikeGrid`}</title>
      <meta
        name="description"
        content={`What ${shop.name} has marked down right now: how much of their range is discounted, the price range they sell at, and the categories they stock. Rebuilt daily from their live catalogue.`}
      />
      <link rel="canonical" href={canonicalFor(shop.path)} />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(buildBreadcrumbJsonLd(trail)) }}
      />

      <nav className="text-sm text-slate-500 mb-6 flex items-center gap-1.5 flex-wrap">
        <Link to="/" className="hover:text-orange-600">Deals</Link>
        <span>/</span>
        <Link to="/shops" className="hover:text-orange-600">Shops</Link>
        {homeCity && (
          <>
            <span>/</span>
            <Link to={backTo} className="hover:text-orange-600">{homeCity}</Link>
          </>
        )}
        <span>/</span>
        <span className="text-slate-400">{shop.name}</span>
      </nav>

      <div className="flex flex-wrap items-start gap-4 mb-6">
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-semibold text-slate-900 tracking-tight mb-1.5">
            {shop.name}
          </h1>
          <p className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-slate-500">
            <span>{shop.cities.length > 1 ? shop.cities.join(', ') : shopWhere(shop)}</span>
            {rank && (
              <span className="inline-flex items-center rounded-full border border-orange-200 bg-orange-50 px-2.5 py-0.5 text-xs font-semibold text-orange-700">
                {ordinal(rank.position)} of {rank.total} {rank.city} shops by share on sale
              </span>
            )}
          </p>
        </div>
        <a
          href={shop.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 bg-orange-600 hover:bg-orange-700 text-white text-sm font-bold rounded-lg px-4 py-2.5 transition-colors"
        >
          Visit {shop.url.replace(/^https?:\/\/(www\.)?/, '')}
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M2.5 6h7M6.5 3l3 3-3 3" />
          </svg>
        </a>
      </div>

      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <Tile label="Bikes listed" value={row?.listings} />
        <Tile label="On sale now" value={row?.onSale} />
        <Tile label="Share on sale" value={row ? `${row.share}%` : undefined} />
        <Tile
          label="Deepest cut"
          value={row ? (row.deepestCut ? `${row.deepestCut}%` : 'none') : undefined}
          accent
        />
      </dl>

      <dl className="flex flex-wrap gap-x-8 gap-y-2 py-3.5 border-y border-slate-200 text-sm text-slate-700 tabular-nums mb-8">
        <Meta label="Prices">
          {priceRange ? `${money(priceRange.min)} to ${money(priceRange.max)}` : '–'}
        </Meta>
        <Meta label="Stocks">{categories.length ? categories.join(', ') : '–'}</Meta>
        <Meta label="Last checked">
          {row?.lastSuccessAt ? formatDayLabel(new Date(row.lastSuccessAt)) : '–'}
        </Meta>
      </dl>

      <h2 className="text-base font-semibold text-slate-800 mb-4">
        Biggest discounts at {shop.name}
      </h2>

      {deals?.results?.length ? (
        <>
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            {deals.results.map((bike) => (
              <BikeCard key={bike.id} bike={bike} />
            ))}
          </div>
          {row && row.onSale > deals.results.length && (
            <p className="mt-5 text-sm">
              <Link
                to={`/deals?vendor=${encodeURIComponent(shop.name)}`}
                className="text-orange-600 hover:text-orange-700 font-medium"
              >
                See all {row.onSale} deals at {shop.name} →
              </Link>
            </p>
          )}
        </>
      ) : (
        <p className="text-slate-600">
          {deals
            ? `${shop.name} has nothing discounted today. Their full range is still on their own site.`
            : `Reading the latest from ${shop.name}…`}
        </p>
      )}

      <p className="mt-10 pt-6 border-t border-slate-200 text-sm">
        <Link to={backTo} className="text-slate-500 hover:text-orange-600">
          ← Back to {homeCity ? `${homeCity} shops` : 'all shops'}
        </Link>
      </p>
    </div>
  )
}

function Tile({ label, value, accent = false }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl px-4 py-3">
      <dt className="text-xs text-slate-400 mb-0.5">{label}</dt>
      <dd
        className={`text-2xl font-semibold tracking-tight tabular-nums ${
          accent ? 'text-emerald-700' : 'text-slate-900'
        }`}
      >
        {/* A dash rather than a spinner: this page is prerendered, so the empty
            shape is what a crawler and the first paint both get. */}
        {value ?? <span className="text-slate-300">–</span>}
      </dd>
    </div>
  )
}

function Meta({ label, children }) {
  return (
    <div>
      <dt className="inline text-slate-400 mr-1.5">{label}</dt>
      <dd className="inline">{children}</dd>
    </div>
  )
}
