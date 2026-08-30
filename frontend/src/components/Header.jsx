import { Link, NavLink } from 'react-router-dom'
import FlagAU from './FlagAU'
import RegionMenu from './RegionMenu'

// The site's whole map, in the one piece of chrome every page shares. It used
// to hold a logo, a search box and a bike count, which said the site only did
// one thing; the guides and the market report were reachable from the footer
// and nowhere else. The icons are the same 16px stroke family as the search,
// heart and hamburger glyphs; only the md+ nav draws them, because the compact
// nav's row has no room to spare at 360px.
const NAV = [
  {
    label: 'Deals',
    to: '/deals',
    icon: (
      <>
        <path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z" />
        <circle cx="7.5" cy="7.5" r=".5" fill="currentColor" />
      </>
    ),
  },
  {
    label: 'Guides',
    to: '/guides',
    icon: (
      <>
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
      </>
    ),
  },
  {
    label: 'Shops',
    to: '/shops',
    icon: (
      <>
        <path d="M3 9l1.5-5h15L21 9" />
        <path d="M3 9h18v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" />
        <path d="M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0" />
      </>
    ),
  },
  {
    label: 'Market',
    to: '/trends',
    icon: (
      <>
        <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
        <polyline points="16 7 22 7 22 13" />
      </>
    ),
  },
]

// `dark` is the feed's shell. Every other route keeps the white header, so the
// prop is what stops the marketing pages from inheriting the tool's chrome.
const navClass = (dark) => ({ isActive }) =>
  `group inline-flex items-center gap-1.5 text-sm transition-colors ${
    isActive
      ? `font-semibold ${dark ? 'text-white' : 'text-slate-900'}`
      : `font-medium ${dark ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-900'}`
  }`

// The label carries the route state through text colour; the icon carries it
// through the accent, warming to orange on hover and staying orange where you
// are, with a one-pixel lift so the hover reads as motion, not just a repaint.
const iconClass = (dark) => (isActive) =>
  `transition group-hover:-translate-y-px ${
    isActive
      ? (dark ? 'text-orange-400' : 'text-orange-600')
      : dark
        ? 'text-slate-500 group-hover:text-orange-400'
        : 'text-slate-400 group-hover:text-orange-600'
  }`

export default function Header({ params, onUpdate, onOpenSidebar, savedCount = 0, dark = false }) {
  const nav = navClass(dark)
  const ico = iconClass(dark)

  return (
    <header
      className={`px-4 sm:px-6 py-2.5 md:h-[var(--header-h)] flex items-center gap-3 sm:gap-6 flex-shrink-0 border-b ${
        dark ? 'bg-navy-900 border-white/10' : 'bg-white border-slate-200'
      }`}
    >
      {onOpenSidebar && (
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open filters"
          className={`md:hidden flex-shrink-0 ${dark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'}`}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>
      )}

      <Link to="/" className="flex items-center gap-1.5 flex-shrink-0">
        <img
          src={dark ? '/logos/bikegrid/bikegrid_white.png' : '/logos/bikegrid/bikegrid-black.png'}
          alt="BikeGrid"
          className="h-8 sm:h-9 w-auto object-contain"
        />
        <FlagAU className={`h-3.5 w-7 rounded-[2px] ring-1 flex-shrink-0 ${dark ? 'ring-white/20' : 'ring-slate-200'}`} />
      </Link>

      <nav aria-label="Main" className="hidden md:flex items-center gap-6 flex-shrink-0">
        {NAV.map(({ label, to, icon }) => (
          <NavLink key={to} to={to} className={nav}>
            {({ isActive }) => (
              <>
                <svg
                  width="16" height="16" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  aria-hidden="true"
                  className={ico(isActive)}
                >
                  {icon}
                </svg>
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {params ? (
        <>
          <div className="flex-1 flex items-center justify-end min-w-0">
            <div className="relative w-full max-w-xs">
              <svg
                className={`absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none ${dark ? 'text-slate-500' : 'text-slate-400'}`}
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
                className={`w-full border rounded-lg pl-9 pr-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition ${
                  dark
                    ? 'bg-white/5 border-white/15 text-white placeholder-slate-500'
                    : 'bg-slate-50 border-slate-200 text-slate-800 placeholder-slate-400'
                }`}
              />
            </div>
          </div>

          <div className="hidden sm:flex items-center gap-3 flex-shrink-0">
            <RegionMenu cities={params.city} onUpdate={onUpdate} dark={dark} />
            {savedCount > 0 && (
              <span
                className={`inline-flex items-center gap-1.5 text-sm ${dark ? 'text-slate-300' : 'text-slate-600'}`}
                title={`${savedCount} saved`}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" className={dark ? 'text-orange-400' : 'text-orange-600'}>
                  <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21.2l7.8-7.8 1-1.1a5.5 5.5 0 0 0 0-7.7z" />
                </svg>
                <span className="tabular-nums">{savedCount}</span>
              </span>
            )}
          </div>
        </>
      ) : (
        <nav aria-label="Main, compact" className="ml-auto flex md:hidden items-center gap-4 flex-shrink-0">
          {NAV.map(({ label, to }) => (
            <NavLink key={to} to={to} className={nav}>
              {label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  )
}
