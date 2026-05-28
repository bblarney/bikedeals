import { Link } from 'react-router-dom'
import { REGIONS } from '../constants'

export default function Header({ total, lastScrapedAt, params, onUpdate, onChangeRegion, onOpenSidebar }) {
  const timeAgo = lastScrapedAt ? formatTimeAgo(new Date(lastScrapedAt)) : null

  const activeRegion = params
    ? REGIONS.find((r) => r.cities.some((c) => params.city?.includes(c)))
    : null
  return (
    <header className="bg-slate-900 px-4 sm:px-6 py-4 flex items-stretch gap-3 sm:gap-6 flex-shrink-0">
      {params && onOpenSidebar && (
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open filters"
          className="md:hidden self-center text-slate-300 hover:text-white"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>
      )}

      <Link to="/" className="flex items-center">
        <img src="/logos/bikegrid/bikegrid_white.png" alt="BikeGrid" className="h-16 sm:h-24 w-auto object-contain" />
      </Link>

      {params && (
        <div className="flex-1 flex flex-col justify-end pb-1">
          <div className="relative flex items-center">
            <div className="hidden sm:absolute sm:inset-0 sm:flex items-center justify-center gap-1">
              {REGIONS.map((r) => (
                <button
                  key={r.abbr}
                  onClick={() => {
                    localStorage.setItem('bikegrid_region', r.name)
                    onUpdate({ city: r.cities })
                  }}
                  className={`text-xs font-medium px-2.5 py-1 rounded-full border transition-colors ${
                    activeRegion?.abbr === r.abbr
                      ? 'bg-blue-600 border-blue-600 text-white'
                      : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white hover:bg-slate-700'
                  }`}
                >
                  {r.abbr}
                </button>
              ))}
            </div>
            <div className="ml-auto relative flex items-center gap-3">
              {total != null && (
                <p className="text-sm text-slate-400">
                  <span className="text-white font-medium">{total.toLocaleString()}</span> in-stock deals
                  {timeAgo && <span className="ml-2 text-slate-600 hidden sm:inline">· updated {timeAgo}</span>}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  )
}

function formatTimeAgo(date) {
  const diff = (Date.now() - date.getTime()) / 1000
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}
