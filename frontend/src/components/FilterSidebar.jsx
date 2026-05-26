import MultiSelectDropdown from './MultiSelectDropdown'

const SIZE_ORDER = ['XS', 'S', 'M', 'L', 'XL', 'XXL']

export default function FilterSidebar({ filters, params, onUpdate }) {
  const { category, city, size, vendor, min_discount, q, sort } = params

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

  const active = hasActiveFilters(params)

  return (
    <aside className="w-60 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col">
      <div className="px-5 py-4 flex items-center justify-between border-b border-slate-100">
        <span className="text-sm font-semibold text-slate-800">Filters</span>
        {active && (
          <button
            onClick={() =>
              onUpdate({ category: '', city: '', size: [], vendor: '', min_discount: 0, q: '' })
            }
            className="text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            Clear all
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        <FilterSection label="Search">
          <input
            type="search"
            placeholder="Brand or model…"
            value={q}
            onChange={(e) => onUpdate({ q: e.target.value })}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
          />
        </FilterSection>

        {filters?.cities?.length > 0 && (
          <FilterSection label="City">
            <StyledSelect value={city} onChange={(v) => onUpdate({ city: v })}>
              <option value="">All cities</option>
              {filters.cities.map((c) => <option key={c} value={c}>{c}</option>)}
            </StyledSelect>
          </FilterSection>
        )}

        {filters?.categories?.length > 0 && (
          <FilterSection label="Category">
            <StyledSelect value={category} onChange={(v) => onUpdate({ category: v })}>
              <option value="">All categories</option>
              {filters.categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </StyledSelect>
          </FilterSection>
        )}

        {sizes.length > 0 && (
          <FilterSection label="Size">
            <MultiSelectDropdown
              label="Sizes"
              options={sizes}
              selected={size}
              onChange={(next) => onUpdate({ size: next })}
            />
          </FilterSection>
        )}

        {filters?.vendors?.length > 0 && (
          <FilterSection label="Shop">
            <StyledSelect value={vendor} onChange={(v) => onUpdate({ vendor: v })}>
              <option value="">All shops</option>
              {filters.vendors.map((v) => <option key={v} value={v}>{v}</option>)}
            </StyledSelect>
          </FilterSection>
        )}

        <FilterSection label={`Min discount — ${min_discount}%`}>
          <input
            type="range"
            min={0}
            max={filters?.discount_range?.max || 80}
            step={5}
            value={min_discount}
            onChange={(e) => onUpdate({ min_discount: parseInt(e.target.value, 10) })}
            className="w-full accent-blue-600 mt-1"
          />
          <div className="flex justify-between text-xs text-slate-400 mt-1">
            <span>0%</span>
            <span>{filters?.discount_range?.max || 80}%</span>
          </div>
        </FilterSection>

        <div className="border-t border-slate-100 pt-5">
          <FilterSection label="Sort by">
            <StyledSelect value={sort} onChange={(v) => onUpdate({ sort: v })}>
              <option value="discount_desc">Biggest discount</option>
              <option value="price_asc">Price: low → high</option>
              <option value="price_desc">Price: high → low</option>
            </StyledSelect>
          </FilterSection>
        </div>
      </div>
    </aside>
  )
}

function FilterSection({ label, children }) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500 mb-2">{label}</p>
      {children}
    </div>
  )
}

function StyledSelect({ value, onChange, children }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition appearance-none"
    >
      {children}
    </select>
  )
}

function hasActiveFilters({ category, city, size, vendor, min_discount, q }) {
  return category || city || size.length > 0 || vendor || min_discount > 0 || q
}
