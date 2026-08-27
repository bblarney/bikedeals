import { NavLink, useSearchParams } from 'react-router-dom'
import { CATEGORIES } from '../content/categories'

// The seam between the two halves of the site: retail chrome above it, the
// filtering tool below. Category is a route rather than a query parameter, so
// these are links and not buttons, and every one of them is a page a crawler
// can reach.
//
// The rest of the query string rides along, because switching category should
// keep the region and price you already chose. `offset` deliberately does not:
// page 7 of road bikes is not page 7 of gravel.
export default function CategoryBar() {
  const [search] = useSearchParams()
  const carried = new URLSearchParams(search)
  carried.delete('offset')
  carried.delete('category')
  const suffix = carried.toString() ? `?${carried}` : ''

  const pill = ({ isActive }) =>
    `flex-shrink-0 px-3 py-1 rounded-full text-sm transition-colors ${
      isActive
        ? 'bg-navy-900 text-white font-bold'
        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
    }`

  return (
    <nav
      aria-label="Bike categories"
      className="bg-white border-b border-slate-200 flex items-center gap-1.5 px-4 sm:px-6 py-2 md:py-0 md:h-[var(--catbar-h)] overflow-x-auto flex-shrink-0"
    >
      <NavLink to={`/deals${suffix}`} end className={pill}>
        All bikes
      </NavLink>
      {CATEGORIES.map((c) => (
        <NavLink key={c.path} to={`${c.path}${suffix}`} className={pill}>
          {c.label}
        </NavLink>
      ))}

      {/* On a phone the header has no room for the main nav, so it lands here,
          past the categories, rather than only in the footer. */}
      <span className="md:hidden flex items-center gap-3 flex-shrink-0 pl-3 ml-1 border-l border-slate-200">
        <NavLink to="/guides" className="text-sm font-medium text-slate-600">Guides</NavLink>
        <NavLink to="/trends" className="text-sm font-medium text-slate-600">Market</NavLink>
      </span>
    </nav>
  )
}
