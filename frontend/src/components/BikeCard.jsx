import { memo } from 'react'
import { api } from '../api/client'
import { VENDOR_LOGOS, BRAND_LOGOS } from '../logos'

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000

const BikeCard = memo(function BikeCard({ bike }) {
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
  } = bike

  const saving = price_original ? Math.round(price_original - price_sale) : null
  const bigDeal = discount_percentage >= 30
  const isNew = scraped_at && new Date(scraped_at).getTime() > Date.now() - SEVEN_DAYS_MS
  const displayModel = model_name.toLowerCase().startsWith(brand.toLowerCase())
    ? model_name.slice(brand.length).trim()
    : model_name

  return (
    <div className="bg-white rounded-xl border border-slate-100 overflow-hidden hover:shadow-md hover:border-slate-200 transition-all duration-150 flex flex-col">
      {/* Image */}
      <div className="relative aspect-square bg-slate-50 flex items-center justify-center p-3">
        {discount_percentage > 0 && (
          <span className={`absolute top-2 left-2 z-10 inline-flex items-center text-xs font-bold px-2 py-0.5 rounded-full ${
            bigDeal ? 'bg-orange-500 text-white' : 'bg-orange-100 text-orange-700'
          }`}>
            {discount_percentage}% off
          </span>
        )}
        {isNew && (
          <span className="absolute top-2 right-2 z-10 inline-flex items-center text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-500 text-white">
            New
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
            onClick={() => api.recordClick(bike.id)}
            className="flex items-center justify-center gap-1.5 w-full bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors"
          >
            View deal
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2.5 6h7M6.5 3l3 3-3 3" />
            </svg>
          </a>
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
