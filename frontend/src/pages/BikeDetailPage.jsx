import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { VENDOR_LOGOS, BRAND_LOGOS } from '../logos'
import { recencyFlags } from '../lib/badges'
import { formatTimeAgo, formatShortDate } from '../lib/time'
import { usePins } from '../hooks/usePins'
import { useStats } from '../hooks/useStats'
import { buildBikeMeta, buildBikeJsonLd } from '../seo'
import RelatedBikes from '../components/RelatedBikes'
import PriceHistoryChart from '../components/PriceHistoryChart'

// Only trust http(s) URLs from scraped third-party data.
function isHttpUrl(value) {
  if (!value) return false
  try {
    const u = new URL(value)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

export default function BikeDetailPage() {
  const { id } = useParams()
  const { data: bike, isLoading, isError, error } = useQuery({
    queryKey: ['bike', id],
    queryFn: () => api.getBike(id),
    retry: (count, err) => err?.status !== 404 && count < 2,
  })
  // Hooks must run unconditionally (before the early returns below).
  const { pinnedIds, togglePin } = usePins()
  const { data: stats } = useStats()

  if (isLoading) return <DetailSkeleton />

  if (isError) {
    const notFound = error?.status === 404
    return (
      <div className="max-w-3xl mx-auto px-6 py-16 text-center">
        <h1 className="text-xl font-semibold text-slate-900 mb-2">
          {notFound ? 'Deal not found' : 'Something went wrong'}
        </h1>
        <p className="text-slate-500 mb-6">
          {notFound
            ? 'This bike may have sold out or been removed.'
            : 'We could not load this deal. Please try again.'}
        </p>
        <Link to="/" className="text-orange-600 hover:underline font-medium">
          ← Back to all deals
        </Link>
      </div>
    )
  }

  const meta = buildBikeMeta(bike)
  const jsonLd = buildBikeJsonLd(bike)
  const safeImageUrl = isHttpUrl(bike.image_url) ? bike.image_url : null
  const safeProductUrl = isHttpUrl(bike.product_url) ? bike.product_url : null
  const saving = bike.price_original ? Math.round(bike.price_original - bike.price_sale) : null
  const flags = recencyFlags(bike)
  const displayModel = bike.model_name.toLowerCase().startsWith(bike.brand.toLowerCase())
    ? bike.model_name.slice(bike.brand.length).trim()
    : bike.model_name
  const specs = [
    bike.category,
    bike.frame_size && `Size ${bike.frame_size}`,
    bike.frame_material,
    bike.drivetrain_groupset,
    bike.weight_grams && `${(bike.weight_grams / 1000).toFixed(1)} kg`,
  ].filter(Boolean)

  // Lowest offer price (in cents, to dodge float wobble). Every shop matching it
  // is a "best price" — ties all win, not just the first row.
  const offers = bike.offers ?? []
  const lowestCents = offers.length
    ? Math.min(...offers.map((o) => Math.round(o.price_sale * 100)))
    : null
  const isBestPrice = (offer) => Math.round(offer.price_sale * 100) === lowestCents

  const isPinned = pinnedIds.has(bike.id)

  // Deal-quality context: how this discount stacks up against the live average.
  const avgDiscount = stats?.avg_discount ?? 0
  const beatsAverage = bike.discount_percentage > 0 && avgDiscount > 0 && bike.discount_percentage > avgDiscount

  // Other frame sizes of the same model.
  const variants = bike.variants ?? []

  // Freshness / sale-timing microcopy from the timestamps we already store.
  const timing = []
  if (bike.discount_started_at) timing.push(`on sale since ${formatShortDate(new Date(bike.discount_started_at))}`)
  if (bike.price_drop_at) timing.push(`price dropped ${formatTimeAgo(new Date(bike.price_drop_at))}`)
  if (bike.last_seen_at) timing.push(`stock checked ${formatTimeAgo(new Date(bike.last_seen_at))}`)

  function recordOpen(bikeId) {
    api.recordClick(bikeId)
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
      <title>{meta.title}</title>
      <meta name="description" content={meta.description} />
      <link rel="canonical" href={meta.canonical} />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Breadcrumb */}
      <nav className="text-sm text-slate-500 mb-6 flex items-center gap-1.5">
        <Link to="/" className="hover:text-orange-600">Deals</Link>
        <span>/</span>
        <Link to={`/?category=${encodeURIComponent(bike.category)}`} className="hover:text-orange-600">
          {bike.category}
        </Link>
        <span>/</span>
        <span className="text-slate-700 truncate">{bike.brand} {displayModel}</span>
      </nav>

      <div className="grid md:grid-cols-2 gap-8">
        {/* Image */}
        <div className="relative aspect-square bg-slate-50 rounded-2xl flex items-center justify-center p-6 border border-slate-100">
          {bike.discount_percentage > 0 && (
            <span className={`absolute top-0 left-0 z-10 text-sm font-bold pl-3 pr-3.5 py-1.5 rounded-br-2xl ${
              bike.discount_percentage >= 30 ? 'bg-orange-600 text-white' : 'bg-orange-100 text-orange-700'
            }`}>
              −{bike.discount_percentage}%
            </span>
          )}
          {(flags.isPriceDrop || flags.isNewDiscount || flags.isNew) && (
            <div className="absolute bottom-3 left-3 z-10 flex flex-col items-start gap-1">
              {flags.isPriceDrop && <Badge className="bg-blue-500 text-white">↓ Price drop</Badge>}
              {flags.isNewDiscount && <Badge className="bg-amber-400 text-amber-900">New sale</Badge>}
              {flags.isNew && <Badge className="bg-emerald-500 text-white">New</Badge>}
            </div>
          )}
          {safeImageUrl ? (
            <img
              src={safeImageUrl}
              alt={`${bike.brand} ${bike.model_name}`}
              className="object-contain w-full h-full mix-blend-multiply"
              onError={(e) => { e.currentTarget.style.display = 'none' }}
            />
          ) : (
            <span className="text-7xl">🚲</span>
          )}
        </div>

        {/* Details */}
        <div className="flex flex-col">
          <LogoImg
            src={BRAND_LOGOS[bike.brand] ?? VENDOR_LOGOS[bike.vendor_name]}
            fallbackSrc={VENDOR_LOGOS[bike.vendor_name]}
            alt={bike.brand}
            className="h-5 w-auto max-w-[80px] object-contain mb-3"
          />
          <div className="flex items-start justify-between gap-3">
            <h1 className="text-2xl font-bold text-slate-900 leading-tight">
              {bike.brand} {displayModel}
            </h1>
            <button
              type="button"
              onClick={() => togglePin(bike)}
              aria-label={isPinned ? 'Remove from saved' : 'Save deal'}
              aria-pressed={isPinned}
              className={`flex-shrink-0 inline-flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg border transition-colors ${
                isPinned
                  ? 'bg-orange-50 border-orange-300 text-orange-600'
                  : 'bg-white border-slate-200 text-slate-500 hover:text-orange-500 hover:border-orange-200'
              }`}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill={isPinned ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
              </svg>
              {isPinned ? 'Saved' : 'Save'}
            </button>
          </div>

          <div className="mt-4 flex items-baseline gap-3">
            <span className="text-3xl font-bold text-slate-900 tracking-tight">
              ${bike.price_sale.toFixed(0)}
            </span>
            {bike.price_original && bike.price_original > bike.price_sale && (
              <span className="text-base text-slate-400 line-through">
                ${bike.price_original.toFixed(0)}
              </span>
            )}
          </div>
          {saving > 0 && (
            <span className="mt-2 inline-block self-start text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full">
              save ${saving.toLocaleString()}
            </span>
          )}

          {/* Deal-quality context vs the live average */}
          {beatsAverage && (
            <p className="mt-2 text-xs text-slate-500">
              <span className="font-semibold text-slate-700">{bike.discount_percentage}% off</span>
              {' '}— beats the {avgDiscount}% average discount right now.
            </p>
          )}

          {/* Size selector — other frame sizes of this model */}
          {variants.length >= 2 && (
            <div className="mt-5">
              <p className="text-xs font-medium text-slate-500 mb-1.5">Available sizes</p>
              <div className="flex flex-wrap gap-1.5">
                {variants.map((v) => {
                  const active = v.bike_id === bike.id
                  return active ? (
                    <span
                      key={v.bike_id}
                      aria-current="true"
                      className="text-sm font-semibold px-3 py-1.5 rounded-lg border border-orange-500 bg-orange-50 text-orange-700"
                    >
                      {v.frame_size}
                    </span>
                  ) : (
                    <Link
                      key={v.bike_id}
                      to={`/bikes/${v.bike_id}`}
                      className="text-sm font-medium px-3 py-1.5 rounded-lg border border-slate-200 text-slate-700 hover:border-orange-300 hover:text-orange-600 transition-colors"
                    >
                      {v.frame_size}
                    </Link>
                  )
                })}
              </div>
            </div>
          )}

          {/* Specs */}
          {specs.length > 0 && (
            <div className="mt-5 flex flex-wrap gap-2">
              {specs.map((s) => (
                <span key={s} className="text-xs font-medium text-slate-600 bg-slate-100 px-2.5 py-1 rounded-md">
                  {s}
                </span>
              ))}
            </div>
          )}

          {/* Primary CTA */}
          <a
            href={safeProductUrl ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => { if (!safeProductUrl) { e.preventDefault(); return } recordOpen(bike.id) }}
            className="mt-6 flex items-center justify-center gap-2 w-full bg-orange-600 hover:bg-orange-700 text-white text-sm font-semibold px-4 py-3 rounded-xl transition-colors"
          >
            View deal at {bike.vendor_name}
            <svg width="13" height="13" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2.5 6h7M6.5 3l3 3-3 3" />
            </svg>
          </a>
          <p className="mt-2 text-xs text-slate-400">
            Listed at {[bike.vendor_name, bike.city].filter(Boolean).join(' · ')}. Confirm price and availability with the shop.
          </p>
          {timing.length > 0 && (
            <p className="mt-1 text-xs text-slate-400">
              {timing.join(' · ').replace(/^./, (c) => c.toUpperCase())}
            </p>
          )}

          <ShareRow url={meta.canonical} title={`${bike.brand} ${displayModel} — $${bike.price_sale.toFixed(0)}`} />
        </div>
      </div>

      {/* Price history — change-events charted over time */}
      <PriceHistoryChart id={bike.id} bike={bike} />

      {/* Cross-shop comparison — always shown for consistency, even at 1 shop */}
      {bike.offers && bike.offers.length >= 1 && (
        <section className="mt-12">
          <h2 className="text-lg font-semibold text-slate-900 mb-1">
            Where to buy
          </h2>
          <p className="text-sm text-slate-500 mb-4">
            {bike.offers.length >= 2
              ? `Currently in stock at ${bike.offers.length} shops — cheapest first.`
              : 'Currently in stock at 1 shop.'}
          </p>
          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                <tr>
                  <th className="text-left font-medium px-4 py-2.5">Shop</th>
                  <th className="text-left font-medium px-4 py-2.5">Size</th>
                  <th className="text-right font-medium px-4 py-2.5">Price</th>
                  <th className="px-4 py-2.5"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {bike.offers.map((offer) => {
                  const offerUrl = isHttpUrl(offer.product_url) ? offer.product_url : null
                  const best = isBestPrice(offer)
                  return (
                    <tr key={offer.bike_id} className={best ? 'bg-emerald-50/60' : 'bg-white'}>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-800">{offer.vendor_name}</div>
                        {offer.city && <div className="text-xs text-slate-400">{offer.city}</div>}
                        {best && bike.offers.length >= 2 && (
                          <span className="inline-block mt-1 text-[11px] font-semibold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                            Best price
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-500">{offer.frame_size}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="font-bold text-slate-900">${offer.price_sale.toFixed(0)}</div>
                        {offer.price_original && offer.price_original > offer.price_sale && (
                          <div className="text-xs text-slate-400 line-through">${offer.price_original.toFixed(0)}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <a
                          href={offerUrl ?? undefined}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => { if (!offerUrl) { e.preventDefault(); return } recordOpen(offer.bike_id) }}
                          className={`inline-flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors ${
                            best
                              ? 'bg-orange-600 hover:bg-orange-700 text-white'
                              : 'border border-slate-200 text-slate-700 hover:bg-slate-50'
                          }`}
                        >
                          View deal
                        </a>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Related deals — internal links that keep users browsing */}
      <RelatedBikes
        title={`More ${bike.brand} deals`}
        params={{ brand: [bike.brand] }}
        excludeId={bike.id}
        pinnedIds={pinnedIds}
        onTogglePin={togglePin}
      />
      <RelatedBikes
        title={`More ${bike.category} deals`}
        params={{ category: [bike.category] }}
        excludeId={bike.id}
        pinnedIds={pinnedIds}
        onTogglePin={togglePin}
      />

      <div className="mt-10">
        <Link to="/" className="text-sm text-orange-600 hover:underline font-medium">
          ← Back to all deals
        </Link>
      </div>
    </div>
  )
}

function Badge({ className = '', children }) {
  return (
    <span className={`inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-full ${className}`}>
      {children}
    </span>
  )
}

function ShareRow({ url, title }) {
  const [copied, setCopied] = useState(false)

  async function share() {
    if (navigator.share) {
      try {
        await navigator.share({ title, url })
        return
      } catch {
        // user cancelled or unsupported — fall through to copy
      }
    }
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard blocked — nothing else we can do silently
    }
  }

  return (
    <button
      type="button"
      onClick={share}
      className="mt-4 inline-flex items-center gap-2 self-start text-sm font-medium text-slate-600 border border-slate-200 rounded-lg px-3 py-2 hover:bg-slate-50 transition-colors"
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
      </svg>
      {copied ? 'Link copied!' : 'Share this deal'}
    </button>
  )
}

function LogoImg({ src, fallbackSrc, alt, className }) {
  if (!src && !fallbackSrc) return null
  return (
    <img
      src={src ?? fallbackSrc}
      alt={alt}
      className={className}
      onError={(e) => {
        if (fallbackSrc && e.currentTarget.src !== fallbackSrc) {
          e.currentTarget.src = fallbackSrc
        } else {
          e.currentTarget.style.display = 'none'
        }
      }}
    />
  )
}

function DetailSkeleton() {
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 animate-pulse">
      <div className="h-4 w-48 bg-slate-200 rounded mb-6" />
      <div className="grid md:grid-cols-2 gap-8">
        <div className="aspect-square bg-slate-100 rounded-2xl" />
        <div className="space-y-4">
          <div className="h-5 w-20 bg-slate-200 rounded" />
          <div className="h-8 w-3/4 bg-slate-200 rounded" />
          <div className="h-10 w-32 bg-slate-200 rounded" />
          <div className="h-12 w-full bg-slate-200 rounded-xl" />
        </div>
      </div>
    </div>
  )
}
