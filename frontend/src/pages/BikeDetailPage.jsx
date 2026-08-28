import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { VENDOR_LOGOS, BRAND_LOGOS } from '../logos'
import { recencyFlags } from '../lib/badges'
import { formatDayLabel, formatShortDate } from '../lib/time'
import { usePins } from '../hooks/usePins'
import { useStats } from '../hooks/useStats'
import { buildBikeMeta, buildBikeJsonLd, serializeJsonLd, canonicalFor } from '../seo'
import RelatedBikes from '../components/RelatedBikes'
import PriceHistoryChart from '../components/PriceHistoryChart'
import { categoryPath } from '../content/categories'
import { GUIDES } from '../content/guides'
import { isHttpUrl } from '../lib/urls'
import { money } from '../lib/money'
import { displayModelName } from '../lib/model'

// BikeGrid does not sell this bike, so the page is not a shop's product page.
// Its job is the comparison: the same bike is often at several shops at once,
// and the gap between the cheapest and the dearest is the reason to be here
// rather than on Google. That number goes above the fold, and the offers table
// is the biggest thing on the page.
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
        {/* Deals churn daily and the API's sitemap has already handed Google
            these URLs, so a sold-out bike is the highest-volume soft 404 on the
            site: the shell is served with a 200 no matter what the API says.
            A static host cannot answer 404 here, but Googlebot executes JS and
            honours a noindex it finds after render, which drops the dead URL
            from the index instead of leaving a thin page in it. */}
        {notFound && <meta name="robots" content="noindex" />}
        {/* main.jsx strips the canonical that functions/bikes/[id].js injected,
            on the assumption that the mounting component re-declares it. This
            branch is the one place that would otherwise render none at all,
            leaving a JS-executing crawler with a head we just emptied. A
            transient API failure must not cost the page its canonical. */}
        {!notFound && <link rel="canonical" href={canonicalFor(`/bikes/${id}`)} />}
        <h1 className="text-xl font-semibold text-slate-900 mb-2">
          {notFound ? 'Deal not found' : 'Something went wrong'}
        </h1>
        <p className="text-slate-500 mb-6">
          {notFound
            ? 'This bike may have sold out or been removed.'
            : 'We could not load this deal. Please try again.'}
        </p>
        <Link to="/deals" className="text-orange-600 hover:underline font-medium">
          &larr; Back to all deals
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
  const displayModel = displayModelName(bike.brand, bike.model_name)

  // Canonical size first: it is what the size filter matches, with the shop's
  // own wording alongside when it differs, because "54cm" and "M" are not
  // interchangeable to someone about to buy.
  const canonicalSize = bike.frame_size_canonical || bike.frame_size
  const sizeLabel =
    canonicalSize && bike.frame_size && bike.frame_size !== canonicalSize
      ? `${canonicalSize} (listed as ${bike.frame_size})`
      : canonicalSize

  // Every offer is in stock by construction (see the API), collapsed to the
  // cheapest listing per shop and already price-ascending.
  const offers = bike.offers ?? []
  const lowestCents = offers.length
    ? Math.min(...offers.map((o) => Math.round(o.price_sale * 100)))
    : null
  const highestCents = offers.length
    ? Math.max(...offers.map((o) => Math.round(o.price_sale * 100)))
    : null
  const isBestPrice = (offer) => Math.round(offer.price_sale * 100) === lowestCents
  const spread = offers.length >= 2 ? (highestCents - lowestCents) / 100 : 0

  const isPinned = pinnedIds.has(bike.id)

  // Deal-quality context: how this discount stacks up against the live average.
  const avgDiscount = stats?.avg_discount ?? 0
  const beatsAverage = bike.discount_percentage > 0 && avgDiscount > 0 && bike.discount_percentage > avgDiscount

  // Other frame sizes of the same model.
  const variants = bike.variants ?? []

  // Freshness / sale-timing microcopy from the timestamps we already store.
  const timing = []
  if (bike.discount_started_at) timing.push(`on sale since ${formatShortDate(new Date(bike.discount_started_at))}`)
  if (bike.price_drop_at) timing.push(`price dropped ${formatDayLabel(new Date(bike.price_drop_at))}`)

  const guide = GUIDES.find((g) => g.category === bike.category)

  function recordOpen(bikeId) {
    api.recordClick(bikeId)
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
      <title>{meta.title}</title>
      <meta name="description" content={meta.description} />
      <link rel="canonical" href={meta.canonical} />
      {/* A sold-out listing still renders (the price history is worth keeping)
          but must not stay in the index advertising a bike nobody can buy.
          functions/bikes/[id].js emits the same tag before JS runs; main.jsx
          strips that one on mount, so this is what keeps it there for a
          JS-executing crawler. Change one and change the other. */}
      {bike.in_stock === false && <meta name="robots" content="noindex" />}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(jsonLd) }}
      />

      <nav className="text-xs text-slate-400 mb-5 flex items-center gap-1.5">
        <Link to="/deals" className="hover:text-orange-600">Deals</Link>
        <span>/</span>
        <Link to={categoryPath(bike.category)} className="hover:text-orange-600">
          {bike.category}
        </Link>
        <span>/</span>
        <span className="text-slate-600 truncate">{bike.brand} {displayModel}</span>
      </nav>

      <div className="grid md:grid-cols-2 gap-8">
        {/* Image */}
        <div className="relative aspect-square bg-slate-50 rounded-2xl flex items-center justify-center p-6 border border-slate-100 md:sticky md:top-6 md:self-start">
          {bike.discount_percentage > 0 && (
            <span className={`absolute top-3 left-3 z-10 tabular-nums text-sm font-semibold px-2 py-1 rounded-lg ${
              bike.discount_percentage >= 30 ? 'bg-orange-600 text-white' : 'bg-orange-50 text-orange-700'
            }`}>
              &minus;{bike.discount_percentage}%
            </span>
          )}
          {(flags.isPriceDrop || flags.isNewDiscount || flags.isNew) && (
            <div className="absolute bottom-3 left-3 z-10 flex flex-col items-start gap-1">
              {flags.isPriceDrop && <Badge className="bg-blue-50 text-blue-700">&darr; Price cut</Badge>}
              {flags.isNewDiscount && <Badge className="bg-amber-50 text-amber-800">New sale</Badge>}
              {flags.isNew && <Badge className="bg-emerald-50 text-emerald-700">New listing</Badge>}
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
            <svg width="180" height="112" viewBox="0 0 64 40" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="text-slate-200" aria-hidden="true">
              <circle cx="14" cy="28" r="10" /><circle cx="50" cy="28" r="10" />
              <path d="M14 28 27 12h16M27 12l5 16M32 28 43 12M32 28h18M24 11h7M40 9h7" />
            </svg>
          )}
        </div>

        {/* Details */}
        <div className="flex flex-col">
          <div className="flex items-center h-5 mb-2">
            <LogoImg
              src={BRAND_LOGOS[bike.brand] ?? VENDOR_LOGOS[bike.vendor_name]}
              fallbackSrc={VENDOR_LOGOS[bike.vendor_name]}
              alt={bike.brand}
              className="h-5 w-auto max-w-[80px] object-contain"
              fallbackText={
                <span className="tabular-nums text-[10px] uppercase tracking-[0.14em] text-slate-400">
                  {bike.brand}
                </span>
              }
            />
          </div>

          <div className="flex items-start justify-between gap-3">
            <h1 className="text-2xl font-bold text-slate-900 leading-tight tracking-tight">
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

          <div className="mt-4 flex items-baseline gap-3 tabular-nums">
            <span className="text-3xl font-semibold text-slate-900 tracking-tight">
              {money(bike.price_sale)}
            </span>
            {bike.price_original && bike.price_original > bike.price_sale && (
              <span className="text-base text-slate-400 line-through">
                {money(bike.price_original)}
              </span>
            )}
            {saving > 0 && (
              <span className="text-sm text-emerald-700">Save {money(saving)}</span>
            )}
          </div>

          {beatsAverage && (
            <p className="mt-1.5 text-xs text-slate-500">
              <span className="font-semibold text-slate-700">{bike.discount_percentage}% off</span>
              {' '}beats the {avgDiscount}% average discount across everything we track right now.
            </p>
          )}

          <p className="mt-3 flex items-center gap-2 text-sm text-slate-600">
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${bike.in_stock === false ? 'bg-slate-300' : 'bg-emerald-500'}`} aria-hidden="true" />
            {bike.in_stock === false ? 'Last seen at' : 'In stock at'}{' '}
            <b className="font-semibold text-slate-900">{bike.vendor_name}</b>
            {bike.city ? `, ${bike.city}` : ''}
            {bike.last_seen_at && (
              <span className="tabular-nums text-[11px] text-slate-400">
                checked {formatDayLabel(new Date(bike.last_seen_at))}
              </span>
            )}
          </p>

          {/* Other frame sizes of this model, with what each one costs: the
              cheapest size is not always the one you landed on. */}
          {variants.length >= 2 && (
            <div className="mt-5">
              <p className="tabular-nums text-[9.5px] uppercase tracking-[0.13em] text-slate-400 mb-1.5">
                Frame size, this shop
              </p>
              <div className="flex flex-wrap gap-1.5">
                {variants.map((v) => {
                  const active = v.bike_id === bike.id
                  const inner = (
                    <>
                      <b className="block text-sm font-bold">{v.frame_size}</b>
                      <span className={`block tabular-nums text-[10px] ${active ? 'text-orange-700/70' : 'text-slate-400'}`}>
                        {money(v.price_sale)}
                      </span>
                    </>
                  )
                  return active ? (
                    <span
                      key={v.bike_id}
                      aria-current="true"
                      className="px-3 py-1.5 rounded-lg border border-orange-500 bg-orange-50 text-orange-700 text-center"
                    >
                      {inner}
                    </span>
                  ) : (
                    <Link
                      key={v.bike_id}
                      to={`/bikes/${v.bike_id}`}
                      className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-700 hover:border-orange-300 hover:text-orange-600 transition-colors text-center"
                    >
                      {inner}
                    </Link>
                  )
                })}
              </div>
            </div>
          )}

          <a
            href={safeProductUrl ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => { if (!safeProductUrl) { e.preventDefault(); return } recordOpen(bike.id) }}
            className="mt-5 flex items-center justify-center gap-2 w-full bg-orange-600 hover:bg-orange-700 text-white text-sm font-bold px-4 py-3 rounded-xl transition-colors"
          >
            View deal at {bike.vendor_name}
            <svg width="13" height="13" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2.5 6h7M6.5 3l3 3-3 3" />
            </svg>
          </a>
          <p className="mt-2 text-xs text-slate-400">
            We do not sell this bike. Confirm the price and availability with the shop.
            {timing.length > 0 && ` ${timing.join(' · ').replace(/^./, (c) => c.toUpperCase())}.`}
          </p>

          {/* What the shop actually published. The blank rows are the point:
              frame material is named on about three fifths of listings and
              groupset on about a third, and a comparison tool that pads its own
              coverage is not one you can trust. Weight is not listed here at
              all: no shop publishes a real one, so the row was blank on every
              bike. See BikeRecord.weight_grams. */}
          <dl className="mt-6 border-t border-slate-100">
            <Spec label="Category" value={bike.category} />
            <Spec label="Frame size" value={sizeLabel} />
            <Spec label="Frame material" value={bike.frame_material} />
            <Spec label="Groupset" value={bike.drivetrain_groupset} />
            <Spec label="First listed" value={bike.scraped_at ? formatShortDate(new Date(bike.scraped_at)) : null} />
          </dl>

          <ShareRow url={meta.canonical} title={`${bike.brand} ${displayModel}, ${money(bike.price_sale)}`} />
        </div>
      </div>

      {/* The comparison. Cheapest first, and the spread named in words, because
          that number is the whole reason to look this up here. */}
      {offers.length >= 1 && (
        <section className="mt-12">
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">
            {offers.length >= 2
              ? `The same bike at ${offers.length} shops`
              : 'Where to buy'}
          </h2>
          <p className="text-sm text-slate-500 mt-1 mb-4">
            {offers.length >= 2 ? (
              spread > 0 ? (
                <>
                  Cheapest first. The spread between the top and bottom of this table is{' '}
                  <b className="tabular-nums font-semibold text-slate-900">{money(spread)}</b>.
                </>
              ) : (
                'Cheapest first. Every shop is asking the same price today.'
              )
            ) : (
              'The only shop we track carrying this listing right now.'
            )}
          </p>
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full min-w-[40rem] text-sm">
              <thead>
                <tr className="bg-slate-50">
                  <Th>Shop</Th>
                  <Th>Size</Th>
                  <Th>Checked</Th>
                  <Th right>Was</Th>
                  <Th right>Now</Th>
                  <Th right>Save</Th>
                  <Th right>Off</Th>
                  <Th><span className="sr-only">Actions</span></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {offers.map((offer) => {
                  const offerUrl = isHttpUrl(offer.product_url) ? offer.product_url : null
                  const best = isBestPrice(offer)
                  const offerSaving = offer.price_original && offer.price_original > offer.price_sale
                    ? offer.price_original - offer.price_sale
                    : 0
                  const cell = 'px-3 py-2.5 align-middle'
                  return (
                    <tr key={offer.bike_id} className={best && offers.length >= 2 ? 'bg-emerald-50/50' : 'bg-white'}>
                      <td className={cell}>
                        <div className="font-semibold text-slate-900 text-[13px]">{offer.vendor_name}</div>
                        <div className="text-xs text-slate-400">
                          {offer.city}
                          {/* Chains list one national catalogue at one price, so
                              they collapse to a single row: say where the rest
                              of the stock is rather than dropping it. */}
                          {offer.location_count > 1 &&
                            `${offer.city ? ' ' : ''}+ ${offer.location_count - 1} other location${offer.location_count > 2 ? 's' : ''}`}
                        </div>
                        {best && offers.length >= 2 && (
                          <span className="inline-block mt-1 tabular-nums text-[10px] font-semibold text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded">
                            Best price
                          </span>
                        )}
                      </td>
                      <td className={`${cell} tabular-nums text-slate-500 text-xs`}>{offer.frame_size}</td>
                      <td className={`${cell} tabular-nums text-[11px] text-slate-400 whitespace-nowrap`}>
                        {offer.last_seen_at ? formatDayLabel(new Date(offer.last_seen_at)) : ''}
                      </td>
                      <td className={`${cell} text-right tabular-nums text-xs text-slate-400 line-through`}>
                        {offer.price_original && offer.price_original > offer.price_sale ? money(offer.price_original) : ''}
                      </td>
                      <td className={`${cell} text-right tabular-nums font-semibold text-slate-900`}>
                        {money(offer.price_sale)}
                      </td>
                      <td className={`${cell} text-right tabular-nums text-xs text-emerald-700`}>
                        {offerSaving > 0 ? money(offerSaving) : ''}
                      </td>
                      <td className={`${cell} text-right`}>
                        {offer.discount_percentage > 0 && (
                          <span className="tabular-nums text-xs font-semibold text-orange-700 bg-orange-50 rounded px-1.5 py-0.5">
                            {offer.discount_percentage}%
                          </span>
                        )}
                      </td>
                      <td className={`${cell} text-right`}>
                        <a
                          href={offerUrl ?? undefined}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => { if (!offerUrl) { e.preventDefault(); return } recordOpen(offer.bike_id) }}
                          className={`inline-flex items-center gap-1 text-xs font-bold px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap ${
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

      <PriceHistoryChart id={bike.id} bike={bike} />

      {/* The one retail-register moment on the page: the guide is what someone
          comparing two bikes $2,500 apart actually needs. */}
      {guide && (
        <Link
          to={guide.path}
          className="mt-12 flex flex-col sm:flex-row sm:items-center gap-4 border border-navy-900 rounded-xl px-5 py-4 bg-slate-50 hover:bg-white transition-colors"
        >
          <div>
            <p className="tabular-nums text-[10px] uppercase tracking-[0.13em] text-orange-600 font-bold">
              From the {guide.label.toLowerCase()} guide
            </p>
            <p className="font-display text-lg font-bold tracking-tight text-slate-900 mt-1">
              {guide.heading.replace(/^The /, 'Read the ')}
            </p>
            <p className="text-sm text-slate-600 mt-0.5 max-w-[58ch]">{guide.cardBlurb}</p>
          </div>
          <span className="sm:ml-auto flex-shrink-0 bg-orange-600 text-white font-bold text-sm rounded-full px-5 py-2.5">
            Read the guide
          </span>
        </Link>
      )}

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
        <Link to={categoryPath(bike.category)} className="text-sm text-orange-600 hover:underline font-bold">
          &larr; Back to {bike.category.toLowerCase()} deals
        </Link>
      </div>
    </div>
  )
}

function Th({ children, right = false }) {
  return (
    <th
      scope="col"
      className={`tabular-nums text-[9.5px] uppercase tracking-[0.12em] text-slate-400 font-medium px-3 py-2.5 whitespace-nowrap ${right ? 'text-right' : 'text-left'}`}
    >
      {children}
    </th>
  )
}

// A spec row that prints the gap rather than hiding it.
function Spec({ label, value }) {
  return (
    <div className="flex items-baseline gap-4 py-1.5 border-b border-slate-50">
      <dt className="tabular-nums text-[9.5px] uppercase tracking-[0.12em] text-slate-400 w-32 flex-shrink-0">
        {label}
      </dt>
      <dd className={`text-[13px] ${value ? 'text-slate-900' : 'text-slate-300'}`}>
        {value || 'Not published by this shop'}
      </dd>
    </div>
  )
}

function Badge({ className = '', children }) {
  return (
    <span className={`inline-flex items-center text-[10.5px] font-bold px-1.5 py-0.5 rounded-md ${className}`}>
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
        // user cancelled or unsupported: fall through to copy
      }
    }
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard blocked: nothing else we can do silently
    }
  }

  return (
    <button
      type="button"
      onClick={share}
      className="mt-5 inline-flex items-center gap-2 self-start text-sm font-medium text-slate-600 border border-slate-200 rounded-lg px-3 py-2 hover:bg-slate-50 transition-colors"
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
      </svg>
      {copied ? 'Link copied' : 'Share this deal'}
    </button>
  )
}

function LogoImg({ src, fallbackSrc, alt, className, fallbackText = null }) {
  if (!src && !fallbackSrc) return fallbackText
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
      <div className="h-3 w-48 bg-slate-200 rounded mb-6" />
      <div className="grid md:grid-cols-2 gap-8">
        <div className="aspect-square bg-slate-100 rounded-2xl" />
        <div className="space-y-4">
          <div className="h-5 w-20 bg-slate-200 rounded" />
          <div className="h-8 w-3/4 bg-slate-200 rounded" />
          <div className="h-10 w-32 bg-slate-200 rounded" />
          <div className="h-12 w-full bg-slate-200 rounded-xl" />
          <div className="h-40 w-full bg-slate-100 rounded" />
        </div>
      </div>
    </div>
  )
}
