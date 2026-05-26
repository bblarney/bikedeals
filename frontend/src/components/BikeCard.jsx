import { VENDOR_LOGOS, BRAND_LOGOS } from '../logos'

export default function BikeCard({ bike }) {
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
  } = bike

  const saving = price_original ? Math.round(price_original - price_sale) : null
  const bigDeal = discount_percentage >= 30
  const displayModel = model_name.toLowerCase().startsWith(brand.toLowerCase())
    ? model_name.slice(brand.length).trim()
    : model_name

  return (
    <div className="flex items-center gap-4 px-5 py-4 bg-white border-b border-slate-100 hover:bg-slate-50/60 transition-colors">
      {/* Brand logo — falls back to vendor logo */}
      <div className="w-24 flex-shrink-0 flex items-center justify-center">
        <LogoImg
          src={BRAND_LOGOS[brand] ?? VENDOR_LOGOS[vendor_name]}
          fallbackSrc={VENDOR_LOGOS[vendor_name]}
          alt={brand}
          className="h-24 w-auto max-w-[96px] object-contain"
        />
      </div>

      {/* Bike image */}
      <div className="group relative w-32 h-32 flex-shrink-0 rounded overflow-visible bg-gray-100 flex items-center justify-center">
        {image_url ? (
          <>
            <img
              src={image_url}
              alt={`${brand} ${model_name}`}
              width={128}
              height={128}
              loading="lazy"
              className="object-contain w-full h-full rounded cursor-zoom-in"
            />
            <div className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-3 z-30 hidden group-hover:block">
              <div className="w-[480px] h-[480px] bg-white border border-gray-200 rounded-lg shadow-xl flex items-center justify-center p-2">
                <img src={image_url} alt={`${brand} ${model_name}`} className="object-contain w-full h-full" />
              </div>
            </div>
          </>
        ) : (
          <span className="text-4xl">🚲</span>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-900 truncate leading-snug">
          {brand} {displayModel}
        </p>
        <p className="text-xs text-slate-500 mt-0.5">
          {category} · Size {frame_size}
        </p>
        <div className="flex items-center gap-1.5 mt-0.5">
          <LogoImg src={VENDOR_LOGOS[vendor_name]} alt={vendor_name} className="h-3.5 w-auto max-w-[40px] object-contain flex-shrink-0" />
          <p className="text-xs text-slate-400 truncate">
            {vendor_name}{city ? ` · ${city}` : ''}
          </p>
        </div>
      </div>

      {/* Discount badge */}
      <div className="flex-shrink-0 text-right min-w-[100px]">
        {discount_percentage > 0 && (
          <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full mb-1.5 ${
            bigDeal ? 'bg-orange-500 text-white' : 'bg-orange-100 text-orange-700'
          }`}>
            {discount_percentage}% off{saving ? ` · $${saving}` : ''}
          </span>
        )}
        <div>
          <span className="text-base font-bold text-slate-900">${price_sale.toFixed(0)}</span>
          {price_original && price_original > price_sale && (
            <span className="text-xs text-slate-400 line-through ml-1.5">${price_original.toFixed(0)}</span>
          )}
        </div>
      </div>

      {/* CTA */}
      <a
        href={product_url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex-shrink-0 ml-1 inline-flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors"
      >
        View deal
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2.5 6h7M6.5 3l3 3-3 3" />
        </svg>
      </a>
    </div>
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
