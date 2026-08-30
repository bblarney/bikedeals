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

  // On the navy shell the active pill can no longer be navy, so the accent
  // takes the job: orange is the only thing on the page brighter than a card.
  const pill = ({ isActive }) =>
    `flex-shrink-0 px-3 py-1 rounded-full text-sm transition-colors ${
      isActive
        ? 'bg-orange-500 text-white font-bold'
        : 'text-slate-400 hover:text-white hover:bg-white/10'
    }`

  return (
    <nav
      aria-label="Bike categories"
      className="bg-navy-900 border-b border-white/10 flex items-center gap-1.5 px-4 sm:px-6 py-2 md:py-0 md:h-[var(--catbar-h)] overflow-x-auto flex-shrink-0"
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
      <span className="md:hidden flex items-center gap-3 flex-shrink-0 pl-3 ml-1 border-l border-white/10">
        <NavLink to="/guides" className="text-sm font-medium text-slate-400 hover:text-white">Guides</NavLink>
        <NavLink to="/shops" className="text-sm font-medium text-slate-400 hover:text-white">Shops</NavLink>
        <NavLink to="/trends" className="text-sm font-medium text-slate-400 hover:text-white">Market</NavLink>
      </span>
    </nav>
  )
}
