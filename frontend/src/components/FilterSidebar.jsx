import { useMemo } from 'react'
import MultiSelectDropdown from './MultiSelectDropdown'
import SidebarAd from './SidebarAd'
import { DEFAULT_FILTERS, REGIONS, SIZE_ORDER } from '../constants'
import { REGION_KEY } from '../lib/landing'

// The instrument panel. Category is not here: it is the route, and the category
// bar above the results owns it.
//
// Two things every dropdown does that it did not before. It carries its live
// option count, which /meta/filters gives away free because each facet already
// excludes itself: "any of 17 shops" is the truth for the filter state you are
// in, and it says how much room is left to narrow. And the two enrichment
// filters carry their coverage, because frame material is published on about
// three fifths of listings and groupset on about a third: filtering by either
// hides most of the catalogue, and a filter that does that quietly is worse
// than one that says so.
export default function FilterSidebar({
  filters,
  params,
  onUpdate,
  mobileOpen = false,
  onCloseMobile,
  desktopCollapsed = false,
  coverage = null,
}) {
  const {
    category, city, size, vendor, brand, frame_material, drivetrain_groupset,
    min_discount, min_price, max_price, added_since, lockedCategory,
  } = params

  const isLoading = filters == null

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

  // On /gravel-bikes the category comes from the route, so it is not something
  // "Clear all" can clear and must not be what makes the button appear.
  const active = hasActiveFilters({ ...params, category: lockedCategory ? [] : category })

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
          md:sticky md:inset-y-auto md:top-0 md:left-auto md:h-[calc(100dvh-var(--chrome-h))]
          md:transform-none md:transition-[width] md:duration-200
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          ${desktopCollapsed ? 'md:w-0 md:min-w-0 md:overflow-hidden md:border-r-0' : 'md:w-[15.5rem]'}`}
      >
        <div className="px-4 py-3 flex items-center justify-between border-b border-slate-100">
          <span className="text-sm font-bold text-slate-900">Filters</span>
          <div className="flex items-center gap-3">
            {active && (
              <button
                onClick={() => onUpdate(DEFAULT_FILTERS)}
                className="text-xs text-orange-600 hover:text-orange-700 font-bold"
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

        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3 flex flex-col gap-3.5">
          <FilterSection label="Region">
            <div className="grid grid-cols-4 gap-1">
              {REGIONS.map((r) => {
                const empty = r.cities.length === 0
                return (
                  <button
                    key={r.abbr}
                    disabled={empty}
                    title={empty ? `No shops in ${r.name} yet` : r.cities.join(', ')}
                    onClick={() => {
                      try {
                        localStorage.setItem(REGION_KEY, r.name)
                      } catch {
                        // Storage blocked. The filter still applies for this visit.
                      }
                      onUpdate({ city: r.cities })
                    }}
                    className={`py-1 rounded-md border text-[11px] font-medium transition-colors text-center ${
                      activeRegion?.abbr === r.abbr
                        ? 'bg-orange-50 border-orange-300 text-orange-700 font-bold'
                        : empty
                          ? 'bg-slate-50 border-slate-200 text-slate-300 cursor-not-allowed'
                          : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                    }`}
                  >
                    {r.abbr}
                  </button>
                )
              })}
            </div>
          </FilterSection>

          <FilterSection label="Date added">
            <div className="grid grid-cols-2 gap-1">
              {[
                { value: 'day', label: 'Last day' },
                { value: 'week', label: 'Last week' },
                { value: 'month', label: 'Last month' },
                { value: 'year', label: 'Last year' },
              ].map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => onUpdate({ added_since: added_since === value ? '' : value })}
                  className={`px-2 py-1 rounded-md border text-[11px] font-medium transition-colors ${
                    added_since === value
                      ? 'bg-orange-50 border-orange-300 text-orange-700 font-bold'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </FilterSection>

          {(isLoading || cityOptions.length > 0) && (
            <Facet
              label="City"
              options={cityOptions}
              selected={city}
              isLoading={isLoading}
              onChange={(next) => onUpdate({ city: next })}
            />
          )}

          <Facet
            label="Size"
            options={sizes}
            selected={size}
            isLoading={isLoading}
            searchable
            onChange={(next) => onUpdate({ size: next })}
          />

          <Facet
            label="Shop"
            options={filters?.vendors ?? []}
            selected={vendor}
            isLoading={isLoading}
            searchable
            onChange={(next) => onUpdate({ vendor: next })}
          />

          <Facet
            label="Brand"
            options={filters?.brands ?? []}
            selected={brand}
            isLoading={isLoading}
            searchable
            onChange={(next) => onUpdate({ brand: next })}
          />

          {(isLoading || filters?.frame_materials?.length > 0) && (
            <Facet
              label="Frame material"
              note={coverage?.frame_material ? `known on ${coverage.frame_material}%` : null}
              options={filters?.frame_materials ?? []}
              selected={frame_material}
              isLoading={isLoading}
              onChange={(next) => onUpdate({ frame_material: next })}
            />
          )}

          {(isLoading || filters?.drivetrain_groupsets?.length > 0) && (
            <Facet
              label="Groupset"
              note={coverage?.drivetrain_groupset ? `known on ${coverage.drivetrain_groupset}%` : null}
              options={filters?.drivetrain_groupsets ?? []}
              selected={drivetrain_groupset}
              isLoading={isLoading}
              searchable
              onChange={(next) => onUpdate({ drivetrain_groupset: next })}
            />
          )}

          <FilterSection label="Price">
            <div className="flex items-center gap-1.5">
              <PriceInput
                value={min_price}
                placeholder={filters?.price_range?.min ? String(Math.floor(filters.price_range.min)) : 'Min'}
                label="Minimum price"
                onChange={(v) => onUpdate({ min_price: v })}
              />
              <span className="text-slate-400 text-xs flex-shrink-0">to</span>
              <PriceInput
                value={max_price}
                placeholder={filters?.price_range?.max ? String(Math.ceil(filters.price_range.max)) : 'Max'}
                label="Maximum price"
                onChange={(v) => onUpdate({ max_price: v })}
              />
            </div>
          </FilterSection>

          <FilterSection
            label="Minimum discount"
            note={<span className={min_discount > 0 ? 'text-orange-700 font-semibold' : ''}>{min_discount}%</span>}
          >
            <input
              type="range"
              min={0}
              max={filters?.discount_range?.max || 80}
              step={5}
              value={min_discount}
              aria-label="Minimum discount"
              onChange={(e) => onUpdate({ min_discount: parseInt(e.target.value, 10) })}
              className="w-full accent-orange-600"
            />
            <div className="flex justify-between tabular-nums text-[10px] text-slate-400 mt-0.5">
              <span>0%</span>
              <span>{filters?.discount_range?.max || 80}%</span>
            </div>
          </FilterSection>

          {/* Only mount the ad when the sidebar is actually shown: a responsive
              unit pushed at 0 width (desktop-collapsed) stays permanently blank. */}
          {!desktopCollapsed && <SidebarAd />}
        </div>
      </aside>
    </>
  )
}

// One facet dropdown, with its live option count standing in for "All shops".
function Facet({ label, options, selected, onChange, isLoading, searchable = false, note = null }) {
  return (
    <FilterSection label={label} note={note}>
      {isLoading ? (
        <Skeleton />
      ) : options.length > 0 ? (
        <MultiSelectDropdown
          label={label}
          options={options}
          selected={selected}
          onChange={onChange}
          searchable={searchable}
          placeholder={`Any of ${options.length}`}
        />
      ) : null}
    </FilterSection>
  )
}

function PriceInput({ value, placeholder, onChange, label }) {
  return (
    <div className="relative flex-1 min-w-0">
      <span className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none tabular-nums">$</span>
      <input
        type="text"
        inputMode="numeric"
        aria-label={label}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full tabular-nums border border-slate-200 rounded-lg pl-5 pr-2 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition"
      />
    </div>
  )
}

function FilterSection({ label, note = null, children }) {
  return (
    <div>
      <p className="tabular-nums text-[9.5px] uppercase tracking-[0.13em] text-slate-400 mb-1.5 flex items-center justify-between gap-2">
        <span>{label}</span>
        {note && <span className="normal-case tracking-normal text-slate-400">{note}</span>}
      </p>
      {children}
    </div>
  )
}

function Skeleton() {
  return <div className="h-8 rounded-lg bg-slate-100 animate-pulse" />
}

function hasActiveFilters({ category, city, size, vendor, brand, frame_material, drivetrain_groupset, min_discount, min_price, max_price, q, added_since }) {
  return category.length > 0 || city.length > 0 || size.length > 0 || vendor.length > 0 || brand.length > 0 || frame_material.length > 0 || drivetrain_groupset.length > 0 || min_discount > 0 || min_price || max_price || q || added_since
}
