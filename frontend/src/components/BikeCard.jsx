import { memo } from 'react'
import { api } from '../api/client'
import { VENDOR_LOGOS, BRAND_LOGOS } from '../logos'

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000

const BikeCard = memo(function BikeCard({ bike, isPinned = false, onTogglePin = () => {}, onSkuFilter = () => {} }) {
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
    scraped_at,
    price_drop_at,
    discount_started_at,
    frame_material,
    drivetrain_groupset,
    sku,
    sku_vendor_count,
  } = bike

  const saving = price_original ? Math.round(price_original - price_sale) : null
  const bigDeal = discount_percentage >= 30
  const cutoff = Date.now() - SEVEN_DAYS_MS
  const isNew = scraped_at && new Date(scraped_at).getTime() > cutoff
  const isPriceDrop = price_drop_at && new Date(price_drop_at).getTime() > cutoff
  const isNewDiscount = discount_started_at && new Date(discount_started_at).getTime() > cutoff
  const displayModel = model_name.toLowerCase().startsWith(brand.toLowerCase())
    ? model_name.slice(brand.length).trim()
    : model_name

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onTogglePin(bike)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onTogglePin(bike) }}
      className={`bg-white rounded-xl border overflow-hidden transition-all duration-150 flex flex-col cursor-pointer ${
        isPinned
          ? 'pin-glow'
          : 'border-slate-100 hover:shadow-md hover:border-slate-200'
      }`}
    >
      {/* Image */}
      <div className="relative aspect-square bg-slate-50 flex items-center justify-center p-3">
        {discount_percentage > 0 && (
          <span className={`absolute top-2 left-2 z-10 inline-flex items-center text-xs font-bold px-2 py-0.5 rounded-full ${
            bigDeal ? 'bg-orange-500 text-white' : 'bg-orange-100 text-orange-700'
          }`}>
            {discount_percentage}% off
          </span>
        )}
        {(isNew || isPriceDrop || isNewDiscount) && (
          <div className="absolute top-2 right-2 z-10 flex flex-col items-end gap-1">
            {isPriceDrop && (
              <span className="inline-flex items-center text-xs font-bold px-2 py-0.5 rounded-full bg-blue-500 text-white">
                ↓ Price drop
              </span>
            )}
            {isNewDiscount && !isPriceDrop && (
              <span className="inline-flex items-center text-xs font-bold px-2 py-0.5 rounded-full bg-amber-400 text-amber-900">
                New sale
              </span>
            )}
            {isNew && !isPriceDrop && !isNewDiscount && (
              <span className="inline-flex items-center text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-500 text-white">
                New
              </span>
            )}
          </div>
        )}
        {isPinned && (
          <span className="absolute bottom-2 right-2 z-10 w-5 h-5 bg-purple-500 rounded-full flex items-center justify-center">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="white" stroke="white" strokeWidth="1">
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
            </svg>
          </span>
        )}
        {image_url ? (
          <img
            src={image_url}
            alt={`${brand} ${model_name}`}
            loading="lazy"
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

        {/* Name */}
        <p className="text-sm font-semibold text-slate-900 line-clamp-2 leading-snug">
          {brand} {displayModel}
        </p>

        {/* Meta */}
        <p className="text-xs text-slate-500 mt-0.5">
          {category} · Size {frame_size}
        </p>
        {(frame_material || drivetrain_groupset) && (
          <p className="text-xs text-slate-400 mt-0.5 truncate">
            {[frame_material, drivetrain_groupset].filter(Boolean).join(' · ')}
          </p>
        )}
        <div className="flex items-center gap-1 mt-0.5">
          <LogoImg
            src={VENDOR_LOGOS[vendor_name]}
            alt={vendor_name}
            className="h-3 w-auto max-w-[32px] object-contain flex-shrink-0"
          />
          <p className="text-xs text-slate-400 truncate">
            {vendor_name}{city ? ` · ${city}` : ''}
          </p>
        </div>

        {/* Price + CTA pinned to bottom */}
        <div className="mt-auto pt-3">
          <div className="flex items-baseline gap-1.5 mb-2">
            <span className="text-base font-bold text-slate-900">${price_sale.toFixed(0)}</span>
            {price_original && price_original > price_sale && (
              <span className="text-xs text-slate-400 line-through">${price_original.toFixed(0)}</span>
            )}
            {saving && (
              <span className="text-xs text-slate-400 ml-auto">save ${saving}</span>
            )}
          </div>
          <a
            href={product_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => { e.stopPropagation(); api.recordClick(bike.id) }}
            className="flex items-center justify-center gap-1.5 w-full bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors"
          >
            View deal
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2.5 6h7M6.5 3l3 3-3 3" />
            </svg>
          </a>
          {sku && sku_vendor_count >= 2 && (
            <button
              onClick={(e) => { e.stopPropagation(); onSkuFilter(sku) }}
              className="flex items-center justify-center w-full mt-1.5 text-xs font-medium text-emerald-700 border border-emerald-200 bg-emerald-50 rounded-lg px-3 py-1.5 hover:bg-emerald-100 transition-colors"
            >
              Show at {sku_vendor_count} shop{sku_vendor_count !== 1 ? 's' : ''}
            </button>
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
