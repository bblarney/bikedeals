import { Link } from 'react-router-dom'
import { REGIONS } from '../constants'

export default function Header({ total, lastScrapedAt, params, onUpdate }) {
  const timeAgo = lastScrapedAt ? formatTimeAgo(new Date(lastScrapedAt)) : null

  const activeRegion = params
    ? REGIONS.find((r) => r.cities.some((c) => params.city?.includes(c)))
    : null
  return (
    <header className="bg-slate-900 px-6 py-4 flex items-center justify-between flex-shrink-0">
      <Link to="/" className="flex items-center gap-3">
        <BikeIcon />
        <span className="text-white font-semibold text-lg tracking-tight">BikeDeals</span>
      </Link>

      {params && (
        <div className="flex items-center gap-1">
          {REGIONS.map((r) => (
            <button
              key={r.abbr}
              onClick={() => {
                localStorage.setItem('bikedeals_region', r.name)
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
      )}

      {total != null && (
        <p className="text-sm text-slate-400">
          <span className="text-white font-medium">{total.toLocaleString()}</span> in-stock deals
          {timeAgo && <span className="ml-2 text-slate-600">· updated {timeAgo}</span>}
        </p>
      )}
    </header>
  )
}

function BikeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="5.5" cy="17.5" r="3.5" />
      <circle cx="18.5" cy="17.5" r="3.5" />
      <path d="M5.5 17.5L9 10h6l2 7.5" />
      <path d="M9 10l4-4 3 4" />
      <path d="M3 10h4" />
    </svg>
  )
}

function formatTimeAgo(date) {
  const diff = (Date.now() - date.getTime()) / 1000
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}
