import { useMemo } from 'react'
import MultiSelectDropdown from './MultiSelectDropdown'
import { DEFAULT_FILTERS, REGIONS } from '../constants'

const SIZE_ORDER = ['XS', 'S', 'M', 'L', 'XL', 'XXL']

export default function FilterSidebar({ filters, params, onUpdate, mobileOpen = false, onCloseMobile }) {
  const { category, city, size, vendor, brand, min_discount, q, added_since } = params

  const activeRegion = useMemo(
    () => REGIONS.find((r) => r.cities.some((c) => city.includes(c))),
    [city],
  )
  const cityOptions = activeRegion ? activeRegion.cities : (filters?.cities ?? [])

  const sizes = useMemo(() => {
    if (!filters?.sizes) return []
    return [...filters.sizes].sort((a, b) => {
      const ai = SIZE_ORDER.indexOf(a)
      const bi = SIZE_ORDER.indexOf(b)
      if (ai !== -1 && bi !== -1) return ai - bi
      if (ai !== -1) return -1
      if (bi !== -1) return 1
      return a.localeCompare(b)
    })
  }, [filters])

  const active = hasActiveFilters(params)

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}
      <aside
        className={`bg-white border-r border-slate-200 flex flex-col flex-shrink-0
          fixed inset-y-0 left-0 z-40 w-72 max-w-[85%] transform transition-transform duration-200
          md:static md:transform-none md:w-60 md:transition-none
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
      <div className="px-5 py-4 flex items-center justify-between border-b border-slate-100">
        <span className="text-sm font-semibold text-slate-800">Filters</span>
        <div className="flex items-center gap-3">
          {active && (
            <button
              onClick={() => onUpdate(DEFAULT_FILTERS)}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              Clear all
            </button>
          )}
          {onCloseMobile && (
            <button
              type="button"
              onClick={onCloseMobile}
              aria-label="Close filters"
              className="md:hidden text-slate-400 hover:text-slate-700"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="6" y1="6" x2="18" y2="18" />
                <line x1="6" y1="18" x2="18" y2="6" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        <FilterSection label="Date added">
          <div className="grid grid-cols-2 gap-1.5">
            {[
              { value: 'day',   label: 'Last day' },
              { value: 'week',  label: 'Last week' },
              { value: 'month', label: 'Last month' },
              { value: 'year',  label: 'Last year' },
            ].map(({ value, label }) => (
              <button
                key={value}
                onClick={() => onUpdate({ added_since: added_since === value ? '' : value })}
                className={`px-2 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                  added_since === value
                    ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                    : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </FilterSection>

        <FilterSection label="Search">
          <input
            type="search"
            placeholder="Brand or model…"
            value={q}
            onChange={(e) => onUpdate({ q: e.target.value })}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
          />
        </FilterSection>

        {cityOptions.length > 0 && (
          <FilterSection label="City">
            <MultiSelectDropdown
              label="Cities"
              options={cityOptions}
              selected={city}
              onChange={(next) => onUpdate({ city: next })}
            />
          </FilterSection>
        )}

        {filters?.categories?.length > 0 && (
          <FilterSection label="Category">
            <MultiSelectDropdown
              label="Categories"
              options={filters.categories}
              selected={category}
              onChange={(next) => onUpdate({ category: next })}
            />
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
            <MultiSelectDropdown
              label="Shops"
              options={filters.vendors}
              selected={vendor}
              onChange={(next) => onUpdate({ vendor: next })}
            />
          </FilterSection>
        )}

        {filters?.brands?.length > 0 && (
          <FilterSection label="Brand">
            <MultiSelectDropdown
              label="Brands"
              options={filters.brands}
              selected={brand}
              onChange={(next) => onUpdate({ brand: next })}
            />
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


      </div>
    </aside>
    </>
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

function hasActiveFilters({ category, city, size, vendor, brand, min_discount, q, added_since }) {
  return category.length > 0 || city.length > 0 || size.length > 0 || vendor.length > 0 || brand.length > 0 || min_discount > 0 || q || added_since
}
