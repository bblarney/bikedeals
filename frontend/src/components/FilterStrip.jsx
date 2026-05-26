const SIZE_ORDER = ['XS', 'S', 'M', 'L', 'XL', 'XXL']

export default function FilterStrip({ filters, params, onUpdate }) {
  const { category, city, size, vendor, min_discount, q, sort } = params

  function sel(key, val) {
    onUpdate({ [key]: val === params[key] ? '' : val })
  }

  const sizes = filters?.sizes
    ? [...filters.sizes].sort((a, b) => {
        const ai = SIZE_ORDER.indexOf(a)
        const bi = SIZE_ORDER.indexOf(b)
        if (ai !== -1 && bi !== -1) return ai - bi
        if (ai !== -1) return -1
        if (bi !== -1) return 1
        return a.localeCompare(b)
      })
    : []

  return (
    <div className="sticky top-0 z-10 bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-screen-xl mx-auto px-4 py-2 flex flex-wrap gap-2 items-center">
        {/* Search */}
        <input
          type="search"
          placeholder="Search brand or model…"
          value={q}
          onChange={(e) => onUpdate({ q: e.target.value })}
          className="border border-gray-300 rounded px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />

        {/* City */}
        {filters?.cities?.length > 0 && (
          <select
            value={city}
            onChange={(e) => onUpdate({ city: e.target.value })}
            className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All cities</option>
            {filters.cities.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        )}

        {/* Category */}
        {filters?.categories?.length > 0 && (
          <select
            value={category}
            onChange={(e) => onUpdate({ category: e.target.value })}
            className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All categories</option>
            {filters.categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        )}

        {/* Size multi-select buttons */}
        {sizes.length > 0 && (
          <div className="flex gap-1">
            {sizes.map((s) => (
              <button
                key={s}
                onClick={() => {
                  const next = size.includes(s)
                    ? size.filter((x) => x !== s)
                    : [...size, s]
                  onUpdate({ size: next })
                }}
                className={`px-2 py-1 text-xs rounded border font-medium transition-colors ${
                  size.includes(s)
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'border-gray-300 text-gray-600 hover:border-blue-400'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Vendor */}
        {filters?.vendors?.length > 0 && (
          <select
            value={vendor}
            onChange={(e) => onUpdate({ vendor: e.target.value })}
            className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All shops</option>
            {filters.vendors.map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        )}

        {/* Min discount */}
        <label className="flex items-center gap-1.5 text-sm text-gray-600">
          <span className="whitespace-nowrap">Min {min_discount}% off</span>
          <input
            type="range"
            min={0}
            max={filters?.discount_range?.max || 80}
            step={5}
            value={min_discount}
            onChange={(e) => onUpdate({ min_discount: parseInt(e.target.value, 10) })}
            className="w-24 accent-blue-600"
          />
        </label>

        {/* Sort */}
        <select
          value={sort}
          onChange={(e) => onUpdate({ sort: e.target.value })}
          className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 ml-auto"
        >
          <option value="discount_desc">Biggest discount</option>
          <option value="price_asc">Price: low → high</option>
          <option value="price_desc">Price: high → low</option>
        </select>

        {/* Clear */}
        {hasActiveFilters(params) && (
          <button
            onClick={() =>
              onUpdate({ category: '', city: '', size: [], vendor: '', min_discount: 0, q: '', sort: 'discount_desc' })
            }
            className="text-xs text-blue-600 hover:underline whitespace-nowrap"
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  )
}

function hasActiveFilters({ category, city, size, vendor, min_discount, q }) {
  return category || city || size.length > 0 || vendor || min_discount > 0 || q
}
