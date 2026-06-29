import { Link } from 'react-router-dom'
import { formatTimeAgo } from '../lib/time'

export default function Header({ total, lastScrapedAt, params, onOpenSidebar }) {
  const timeAgo = lastScrapedAt ? formatTimeAgo(new Date(lastScrapedAt)) : null

  return (
    <header className="bg-navy-900 px-4 sm:px-6 py-2.5 flex items-center gap-3 sm:gap-5 flex-shrink-0">
      {params && onOpenSidebar && (
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open filters"
          className="md:hidden text-slate-300 hover:text-white flex-shrink-0"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>
      )}

      <Link to="/" className="flex items-center gap-1.5 flex-shrink-0">
        <img src="/logos/bikegrid/bikegrid_white.png" alt="BikeGrid" className="h-9 sm:h-11 w-auto object-contain" />
        <span className="text-[10px] font-semibold tracking-wide px-1.5 py-0.5 rounded-full bg-orange-500/15 border border-orange-500/30 text-orange-400">AU</span>
      </Link>

      {params && (
        <>
          <div className="flex-1 flex items-center min-w-0">
            <div className="relative w-full max-w-md">
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"
                width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              >
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
              </svg>
              <input
                type="search"
                value={params.q}
                onChange={(e) => params.update({ q: e.target.value })}
                placeholder="Search brand or model…"
                aria-label="Search deals"
                className="w-full bg-navy-800 border border-navy-700 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition"
              />
            </div>
          </div>

          {total != null && (
            <p className="hidden sm:block text-sm text-slate-400 flex-shrink-0">
              <span className="text-white font-medium">{total.toLocaleString()}</span> deals
              {timeAgo && <span className="ml-2 text-slate-600">· updated {timeAgo}</span>}
            </p>
          )}
        </>
      )}
    </header>
  )
}
