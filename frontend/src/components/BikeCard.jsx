import { memo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { VENDOR_LOGOS, BRAND_LOGOS } from '../logos'
import { recencyFlags } from '../lib/badges'

// Image and product URLs come from scraped third-party data. Only trust http(s)
// sources (defence-in-depth against javascript:/data: and other schemes).
function isHttpUrl(value) {
  if (!value) return false
  try {
    const u = new URL(value)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

const BikeCard = memo(function BikeCard({ bike, isPinned = false, onTogglePin = () => {} }) {
  const {
    brand,
    model_name,
    frame_size,
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
    sku,
    sku_vendor_count,
  } = bike

  const navigate = useNavigate()
  const safeImageUrl = isHttpUrl(image_url) ? image_url : null
  const safeProductUrl = isHttpUrl(product_url) ? product_url : null
  const saving = price_original ? Math.round(price_original - price_sale) : null
  const bigDeal = discount_percentage >= 30
  const { isPriceDrop, isNewDiscount, isNew } = recencyFlags(bike)
  const displayModel = model_name.toLowerCase().startsWith(brand.toLowerCase())
    ? model_name.slice(brand.length).trim()
    : model_name

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
          : 'border-slate-100 hover:shadow-md hover:border-slate-200'
      }`}
    >
      {/* Image */}
      <div className="relative aspect-square bg-slate-50 flex items-center justify-center p-3">
        {/* Discount ribbon — colour encodes magnitude */}
        {discount_percentage > 0 && (
          <span className={`absolute top-0 left-0 z-10 inline-flex items-center text-xs font-bold pl-2 pr-2.5 py-1 rounded-br-xl ${
            bigDeal ? 'bg-orange-600 text-white' : 'bg-orange-100 text-orange-700'
          }`}>
            −{discount_percentage}%
          </span>
        )}

        {/* Save / pin */}
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onTogglePin(bike) }}
          aria-label={isPinned ? 'Remove from saved' : 'Save deal'}
          aria-pressed={isPinned}
          className={`absolute top-2 right-2 z-10 w-7 h-7 flex items-center justify-center rounded-full border transition-colors ${
            isPinned
              ? 'bg-orange-50 border-orange-300 text-orange-600'
              : 'bg-white/90 border-slate-200 text-slate-400 hover:text-orange-500 hover:border-orange-200'
          }`}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill={isPinned ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
          </svg>
        </button>

        {/* Recency badges — distinct from the discount/save signals */}
        {(isPriceDrop || isNewDiscount || isNew) && (
          <div className="absolute bottom-2 left-2 z-10 flex flex-col items-start gap-1">
            {isPriceDrop && (
              <span className="inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-full bg-blue-500 text-white">
                ↓ Price drop
              </span>
            )}
            {isNewDiscount && (
              <span className="inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-full bg-amber-400 text-amber-900">
                New sale
              </span>
            )}
            {isNew && (
              <span className="inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-500 text-white">
                New
              </span>
            )}
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
          <span className="text-5xl">🚲</span>
        )}
      </div>

      {/* Content */}
      <div className="flex flex-col flex-1 p-3">
        {/* Brand logo */}
        <div className="flex items-center gap-1.5 mb-1.5 h-5">
          <LogoImg
            src={BRAND_LOGOS[brand] ?? VENDOR_LOGOS[vendor_name]}
            fallbackSrc={VENDOR_LOGOS[vendor_name]}
            alt={brand}
            className="h-4 w-auto max-w-[64px] object-contain"
          />
        </div>

        {/* Name — links to the detail / price-comparison page */}
        <Link
          to={`/bikes/${bike.id}`}
          onClick={(e) => e.stopPropagation()}
          className="text-sm font-semibold text-slate-900 line-clamp-2 leading-snug hover:text-orange-600"
        >
          {brand} {displayModel}
        </Link>

        {/* Price — the hero */}
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-xl font-bold text-slate-900 tracking-tight">${price_sale.toFixed(0)}</span>
          {price_original && price_original > price_sale && (
            <span className="text-xs text-slate-400 line-through">${price_original.toFixed(0)}</span>
          )}
        </div>
        {saving > 0 && (
          <span className="mt-1.5 inline-block self-start text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
            save ${saving.toLocaleString()}
          </span>
        )}

        {/* Shop + spec line */}
        <div className="flex items-center gap-1.5 mt-2 text-xs text-slate-500 min-w-0">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0 text-slate-400">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
          </svg>
          <span className="truncate">
            {vendor_name}{city ? ` · ${city}` : ''}
          </span>
        </div>
        <p className="text-xs text-slate-400 mt-0.5 truncate">
          {[category, frame_size && `Size ${frame_size}`, frame_material, drivetrain_groupset].filter(Boolean).join(' · ')}
        </p>

        {/* CTA pinned to bottom */}
        <div className="mt-auto pt-3">
          <a
            href={safeProductUrl ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => { e.stopPropagation(); if (!safeProductUrl) { e.preventDefault(); return } api.recordClick(bike.id) }}
            className="flex items-center justify-center gap-1.5 w-full bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors"
          >
            View deal
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2.5 6h7M6.5 3l3 3-3 3" />
            </svg>
          </a>
          {sku && sku_vendor_count >= 2 && (
            <Link
              to={`/bikes/${bike.id}`}
              onClick={(e) => e.stopPropagation()}
              className="flex items-center justify-center w-full mt-1.5 text-xs font-medium text-emerald-700 border border-emerald-200 bg-emerald-50 rounded-lg px-3 py-1.5 hover:bg-emerald-100 transition-colors"
            >
              Compare {sku_vendor_count} shop{sku_vendor_count !== 1 ? 's' : ''}
            </Link>
          )}
        </div>
      </div>
    </div>
  )
})

export default BikeCard

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
