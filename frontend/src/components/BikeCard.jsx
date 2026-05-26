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

  return (
    <div className="flex items-center gap-4 px-5 py-3.5 bg-white border-b border-slate-100 hover:bg-slate-50/60 transition-colors">
      {/* Image */}
      <div className="group relative w-16 h-16 flex-shrink-0 rounded overflow-visible bg-gray-100 flex items-center justify-center">
        {image_url ? (
          <>
            <img
              src={image_url}
              alt={`${brand} ${model_name}`}
              width={64}
              height={64}
              loading="lazy"
              className="object-contain w-full h-full rounded cursor-zoom-in"
            />
            <div className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-3 z-30 hidden group-hover:block">
              <div className="w-52 h-52 bg-white border border-gray-200 rounded-lg shadow-xl flex items-center justify-center p-2">
                <img src={image_url} alt={`${brand} ${model_name}`} className="object-contain w-full h-full" />
              </div>
            </div>
          </>
        ) : (
          <span className="text-2xl">🚲</span>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-900 truncate leading-snug">
          {brand} {model_name}
        </p>
        <p className="text-xs text-slate-500 mt-0.5">
          {category} · Size {frame_size}
        </p>
        <p className="text-xs text-slate-400 mt-0.5 truncate">
          {vendor_name}{city ? ` · ${city}` : ''}
        </p>
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
