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

  const saving = price_original ? price_original - price_sale : null

  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-100 hover:bg-gray-50 transition-colors">
      {/* Image */}
      <div className="w-16 h-16 flex-shrink-0 rounded overflow-hidden bg-gray-100 flex items-center justify-center">
        {image_url ? (
          <img
            src={image_url}
            alt={`${brand} ${model_name}`}
            width={64}
            height={64}
            loading="lazy"
            className="object-contain w-full h-full"
          />
        ) : (
          <span className="text-2xl">🚲</span>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900 truncate">
          {brand} {model_name}
        </p>
        <p className="text-xs text-gray-500">
          {category} · Size {frame_size}
        </p>
        <p className="text-xs text-gray-400 mt-0.5 truncate">
          {vendor_name}
          {city ? ` · ${city}` : ''}
        </p>
      </div>

      {/* Price + badge */}
      <div className="flex-shrink-0 text-right">
        {discount_percentage > 0 && (
          <span className="inline-block bg-red-100 text-red-700 text-xs font-bold px-1.5 py-0.5 rounded mb-1">
            {discount_percentage}% OFF
            {saving ? ` · Save $${Math.round(saving)}` : ''}
          </span>
        )}
        <p className="text-sm font-bold text-gray-900">${price_sale.toFixed(0)}</p>
        {price_original && price_original > price_sale && (
          <p className="text-xs text-gray-400 line-through">${price_original.toFixed(0)}</p>
        )}
      </div>

      {/* CTA */}
      <a
        href={product_url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex-shrink-0 ml-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-2 rounded transition-colors whitespace-nowrap"
      >
        View Deal →
      </a>
    </div>
  )
}
