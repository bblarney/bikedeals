import { Link, NavLink } from 'react-router-dom'
import FlagAU from './FlagAU'
import RegionMenu from './RegionMenu'

// The site's whole map, in the one piece of chrome every page shares. It used
// to hold a logo, a search box and a bike count, which said the site only did
// one thing; the guides and the market report were reachable from the footer
// and nowhere else.
const NAV = [
  { label: 'Deals', to: '/deals' },
  { label: 'Guides', to: '/guides' },
  { label: 'Market', to: '/trends' },
]

const navClass = ({ isActive }) =>
  `text-sm transition-colors ${
    isActive ? 'font-bold text-slate-900' : 'font-medium text-slate-600 hover:text-slate-900'
  }`

export default function Header({ params, onUpdate, onOpenSidebar, savedCount = 0 }) {
  return (
    <header className="bg-white border-b border-slate-200 px-4 sm:px-6 py-2.5 md:h-[var(--header-h)] flex items-center gap-3 sm:gap-6 flex-shrink-0">
      {onOpenSidebar && (
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open filters"
          className="md:hidden text-slate-500 hover:text-slate-900 flex-shrink-0"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>
      )}

      <Link to="/" className="flex items-center gap-1.5 flex-shrink-0">
        <img src="/logos/bikegrid/bikegrid-black.png" alt="BikeGrid" className="h-8 sm:h-9 w-auto object-contain" />
        <FlagAU className="h-3.5 w-7 rounded-[2px] ring-1 ring-slate-200 flex-shrink-0" />
      </Link>

      <nav aria-label="Main" className="hidden md:flex items-center gap-6 flex-shrink-0">
        {NAV.map(({ label, to }) => (
          <NavLink key={to} to={to} className={navClass}>
            {label}
          </NavLink>
        ))}
      </nav>

      {params ? (
        <>
          <div className="flex-1 flex items-center justify-end min-w-0">
            <div className="relative w-full max-w-xs">
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
                width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              >
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
              </svg>
              <input
                type="search"
                value={params.q}
                onChange={(e) => onUpdate({ q: e.target.value })}
                placeholder="Search brand or model…"
                aria-label="Search deals"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition"
              />
            </div>
          </div>

          <div className="hidden sm:flex items-center gap-3 flex-shrink-0">
            <RegionMenu cities={params.city} onUpdate={onUpdate} />
            {savedCount > 0 && (
              <span className="inline-flex items-center gap-1.5 text-sm text-slate-600" title={`${savedCount} saved`}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" className="text-orange-600">
                  <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21.2l7.8-7.8 1-1.1a5.5 5.5 0 0 0 0-7.7z" />
                </svg>
                <span className="font-mono tabular-nums">{savedCount}</span>
              </span>
            )}
          </div>
        </>
      ) : (
        <nav aria-label="Main, compact" className="ml-auto flex md:hidden items-center gap-4 flex-shrink-0">
          {NAV.map(({ label, to }) => (
            <NavLink key={to} to={to} className={navClass}>
              {label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  )
}
