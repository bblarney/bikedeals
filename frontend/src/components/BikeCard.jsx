import { memo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { VENDOR_LOGOS, BRAND_LOGOS } from '../logos'
import { recencyFlags } from '../lib/badges'
import { isHttpUrl } from '../lib/urls'

// Enough chips to read a size run (XS-XL is six) without the row wrapping to a
// third line on a phone; the rest become a "+N".
const MAX_SIZE_CHIPS = 5

const money = (n) => `$${Math.round(n).toLocaleString('en-AU')}`

const BikeCard = memo(function BikeCard({ bike, isPinned = false, onTogglePin = () => {} }) {
  const {
    brand,
    model_name,
    frame_size_canonical,
    category,
    price_sale,
    price_original,
    discount_percentage,
    vendor_name,
    city,
    product_url,
    image_url,
    frame_material,
    drivetrain_groupset,
    product_key,
    sku_vendor_count,
    location_count = 1,
    sizes = [],
  } = bike

  const navigate = useNavigate()
  const safeImageUrl = isHttpUrl(image_url) ? image_url : null
  const safeProductUrl = isHttpUrl(product_url) ? product_url : null
  const saving = price_original && price_original > price_sale ? price_original - price_sale : 0
  const bigDeal = discount_percentage >= 30
  const { isPriceDrop, isNewDiscount, isNew } = recencyFlags(bike)
  const displayModel = model_name.toLowerCase().startsWith(brand.toLowerCase())
    ? model_name.slice(brand.length).trim()
    : model_name

  // One card is one product, so the sizes behind it go in a chip row. A single
  // size stays in the spec line below: a lone chip looks like a filter you can
  // press, and none of them are pressable.
  // Null when the shop's own size names nothing usable ("N/A", "One Size").
  const displaySize = frame_size_canonical
  const sizeChips = sizes.length > 1 ? sizes : []
  const shownChips = sizeChips.slice(0, MAX_SIZE_CHIPS)
  const hiddenChipCount = sizeChips.length - shownChips.length

  // What the shop actually published. Frame material is missing on about two
  // fifths of listings and groupset on two thirds, so the gap is stated rather
  // than left as an empty row: a comparison tool that pads its own coverage is
  // not one you can trust.
  const spec = [frame_material, drivetrain_groupset].filter(Boolean)

  // The card body opens the detail / comparison page. Outbound shop links live
  // on the explicit "View deal" button (and the detail page CTAs), which record
  // the click; navigating to details is not an outbound click, so we don't.
  function openDetails() {
    navigate(`/bikes/${bike.id}`)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={openDetails}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDetails() } }}
      className={`group bg-white rounded-xl border overflow-hidden transition-all duration-150 flex flex-col cursor-pointer ${
        isPinned
          ? 'saved-glow'
          : 'border-slate-200 hover:shadow-md hover:border-slate-300'
      }`}
    >
      {/* Image */}
      <div className="relative aspect-[5/4] bg-slate-50 flex items-center justify-center p-3">
        {discount_percentage > 0 && (
          <span className={`absolute top-2 left-2 z-10 inline-flex items-center font-mono tabular-nums text-[11.5px] font-semibold px-1.5 py-0.5 rounded-md ${
            bigDeal ? 'bg-orange-600 text-white' : 'bg-orange-50 text-orange-700'
          }`}>
            &minus;{discount_percentage}%
          </span>
        )}

        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onTogglePin(bike) }}
          aria-label={isPinned ? 'Remove from saved' : 'Save deal'}
          aria-pressed={isPinned}
          className={`absolute top-2 right-2 z-10 w-7 h-7 flex items-center justify-center rounded-full transition-colors ${
            isPinned
              ? 'bg-orange-50 text-orange-600'
              : 'bg-white/80 text-slate-300 hover:text-orange-500'
          }`}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill={isPinned ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
          </svg>
        </button>

        {/* Recency, from the timestamps the scrape already records */}
        {(isPriceDrop || isNewDiscount || isNew) && (
          <div className="absolute bottom-2 left-2 z-10">
            {isPriceDrop && <Flag className="bg-blue-50 text-blue-700">&darr; Price cut</Flag>}
            {isNewDiscount && <Flag className="bg-amber-50 text-amber-800">New sale</Flag>}
            {isNew && <Flag className="bg-emerald-50 text-emerald-700">New listing</Flag>}
          </div>
        )}

        {safeImageUrl ? (
          <img
            src={safeImageUrl}
            alt={`${brand} ${model_name}`}
            loading="lazy"
            onError={(e) => { e.currentTarget.style.display = 'none' }}
            className="object-contain w-full h-full mix-blend-multiply"
          />
        ) : (
          <svg width="72" height="45" viewBox="0 0 64 40" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-slate-200" aria-hidden="true">
            <circle cx="14" cy="28" r="10" /><circle cx="50" cy="28" r="10" />
            <path d="M14 28 27 12h16M27 12l5 16M32 28 43 12M32 28h18M24 11h7M40 9h7" />
          </svg>
        )}
      </div>

      {/* Content */}
      <div className="flex flex-col flex-1 p-3">
        {/* The brand, as its mark where we have one and as its name where we
            don't, in a fixed-height row so cards line up either way. */}
        <div className="flex items-center h-4 mb-1.5">
          <LogoImg
            src={BRAND_LOGOS[brand] ?? VENDOR_LOGOS[vendor_name]}
            fallbackSrc={VENDOR_LOGOS[vendor_name]}
            alt={brand}
            className="h-4 w-auto max-w-[64px] object-contain"
            fallbackText={
              <span className="font-mono text-[9.5px] uppercase tracking-[0.11em] text-slate-400 truncate">
                {brand}
              </span>
            }
          />
        </div>

        <Link
          to={`/bikes/${bike.id}`}
          onClick={(e) => e.stopPropagation()}
          className="text-[13.5px] font-bold text-slate-900 line-clamp-2 leading-snug tracking-tight hover:text-orange-600"
        >
          {brand} {displayModel}
        </Link>

        {/* Price: mono and tabular, so a column of cards reads as a column of
            numbers rather than as five different typefaces. */}
        <div className="mt-2 flex items-baseline gap-2 font-mono tabular-nums">
          <span className="text-base font-semibold text-slate-900 tracking-tight">{money(price_sale)}</span>
          {price_original && price_original > price_sale && (
            <span className="text-[11px] text-slate-400 line-through">{money(price_original)}</span>
          )}
        </div>
        {saving > 0 && (
          <span className="font-mono tabular-nums text-[11px] text-emerald-700 mt-0.5">
            Save {money(saving)}
          </span>
        )}

        <div className="flex flex-wrap gap-1 mt-2">
          {category && <Chip>{category}</Chip>}
          {spec.map((s) => <Chip key={s}>{s}</Chip>)}
          {spec.length === 0 && <Chip dashed>no spec published</Chip>}
          {sizeChips.length === 0 && displaySize && <Chip>Size {displaySize}</Chip>}
        </div>

        {sizeChips.length > 0 && (
          <div className="flex flex-wrap items-center gap-1 mt-1.5">
            <span className="sr-only">Sizes available: {sizeChips.join(', ')}</span>
            {shownChips.map((size) => (
              <span
                key={size}
                aria-hidden="true"
                className="inline-block font-mono text-[10px] leading-none text-slate-500 bg-slate-50 border border-slate-200 rounded px-1.5 py-1"
              >
                {size}
              </span>
            ))}
            {hiddenChipCount > 0 && (
              <span aria-hidden="true" className="font-mono text-[10px] leading-none text-slate-400">
                +{hiddenChipCount}
              </span>
            )}
          </div>
        )}

        {/* A chain's storefronts collapse to one card, so name the city shown
            and count the rest rather than repeating the listing per city. */}
        <div className="flex items-center gap-1.5 mt-2 text-[11.5px] text-slate-500 min-w-0">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0 text-slate-400">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
          </svg>
          <span className="truncate">
            {vendor_name}{city ? ` · ${city}` : ''}
            {location_count > 1 ? ` +${location_count - 1} more` : ''}
          </span>
        </div>

        <div className="mt-auto pt-3">
          <a
            href={safeProductUrl ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => { e.stopPropagation(); if (!safeProductUrl) { e.preventDefault(); return } api.recordClick(bike.id) }}
            className="flex items-center justify-center gap-1.5 w-full bg-orange-600 hover:bg-orange-700 text-white text-xs font-bold px-3 py-2 rounded-lg transition-colors"
          >
            View deal
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2.5 6h7M6.5 3l3 3-3 3" />
            </svg>
          </a>
        </div>
      </div>

      {/* The cross-shop strip: the one line that says why this site exists
          rather than a shop's own listing page. */}
      {product_key && sku_vendor_count >= 2 && (
        <Link
          to={`/bikes/${bike.id}`}
          onClick={(e) => e.stopPropagation()}
          className="flex items-center gap-1.5 border-t border-slate-100 bg-emerald-50/60 px-3 py-1.5 text-[11px] text-emerald-800 hover:bg-emerald-50 transition-colors"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0">
            <path d="M3 9 4.5 4h15L21 9M3 9h18v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1zM3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0" />
          </svg>
          At <b className="font-mono font-semibold">{sku_vendor_count} shops</b>, compare prices
        </Link>
      )}
    </div>
  )
})

export default BikeCard

function Chip({ children, dashed = false }) {
  return (
    <span className={`inline-block text-[10.5px] leading-none rounded px-1.5 py-1 border ${
      dashed ? 'border-dashed border-slate-200 text-slate-400' : 'border-slate-200 text-slate-600'
    }`}>
      {children}
    </span>
  )
}

function Flag({ className, children }) {
  return (
    <span className={`inline-flex items-center text-[10.5px] font-bold px-1.5 py-0.5 rounded-md ${className}`}>
      {children}
    </span>
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
