import { useEffect, useRef, useState } from 'react'
import { REGIONS } from '../constants'
import { REGION_KEY } from '../lib/landing'

// Region used to be a gate: a full-page picker that stood between every first
// visit and the site. It is a filter, so it lives in the header as one.
//
// Only regions with cities are offered. NT has no shops in the registry yet, so
// picking it would empty the feed with no way to tell why.
const PICKABLE = REGIONS.filter((r) => r.cities.length > 0)

function currentRegion(cities) {
  if (!cities?.length) return null
  return PICKABLE.find((r) => r.cities.some((c) => cities.includes(c))) ?? null
}

export default function RegionMenu({ cities = [], onUpdate }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const region = currentRegion(cities)

  useEffect(() => {
    if (!open) return
    function onDocClick(e) {
      if (!ref.current?.contains(e.target)) setOpen(false)
    }
    function onKey(e) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  function pick(next) {
    try {
      localStorage.setItem(REGION_KEY, next ? next.name : '__all__')
    } catch {
      // Storage blocked. The filter still applies for this visit.
    }
    onUpdate({ city: next ? next.cities : [] })
    setOpen(false)
  }

  // More than one city selected by hand, from the sidebar's city dropdown.
  const label = region
    ? region.name
    : cities.length === 1
      ? cities[0]
      : cities.length > 1
        ? `${cities.length} cities`
        : 'All of Australia'

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="inline-flex items-center gap-1.5 border border-slate-200 rounded-full pl-2.5 pr-2 py-1 text-sm text-slate-700 hover:border-slate-300 transition-colors max-w-[11rem]"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400 flex-shrink-0">
          <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z" /><circle cx="12" cy="10" r="3" />
        </svg>
        <span className="truncate">{label}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400 flex-shrink-0">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute right-0 top-full mt-1.5 z-50 w-56 bg-white border border-slate-200 rounded-xl shadow-lg py-1.5 max-h-[70vh] overflow-y-auto"
        >
          <li>
            <button
              type="button"
              role="option"
              aria-selected={!region && cities.length === 0}
              onClick={() => pick(null)}
              className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-50 ${
                !region && cities.length === 0 ? 'text-orange-600 font-semibold' : 'text-slate-700'
              }`}
            >
              All of Australia
            </button>
          </li>
          <li aria-hidden="true" className="my-1 border-t border-slate-100" />
          {PICKABLE.map((r) => (
            <li key={r.abbr}>
              <button
                type="button"
                role="option"
                aria-selected={region?.abbr === r.abbr}
                onClick={() => pick(r)}
                className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-50 ${
                  region?.abbr === r.abbr ? 'text-orange-600 font-semibold' : 'text-slate-700'
                }`}
              >
                {r.name}
                <span className="block text-xs text-slate-400 truncate">{r.cities.join(', ')}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
