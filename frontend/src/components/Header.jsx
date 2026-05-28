import { Link } from 'react-router-dom'
import { REGIONS } from '../constants'

export default function Header({ total, lastScrapedAt, params, onUpdate }) {
  const timeAgo = lastScrapedAt ? formatTimeAgo(new Date(lastScrapedAt)) : null

  const activeRegion = params
    ? REGIONS.find((r) => r.cities.some((c) => params.city?.includes(c)))
    : null
  return (
    <header className="bg-slate-900 px-6 py-4 flex items-stretch gap-6 flex-shrink-0">
      <Link to="/" className="flex items-center">
        <img src="/logos/bikegrid/bikegrid_white.png" alt="BikeGrid" className="h-24 w-auto object-contain" />
      </Link>

      {params && (
        <div className="flex-1 flex flex-col justify-end pb-1">
          <div className="relative flex items-center">
            <div className="absolute inset-0 flex items-center justify-center gap-1">
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
            {total != null && (
              <p className="text-sm text-slate-400 ml-auto relative">
                <span className="text-white font-medium">{total.toLocaleString()}</span> in-stock deals
                {timeAgo && <span className="ml-2 text-slate-600">· updated {timeAgo}</span>}
              </p>
            )}
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
