export default function Header({ total, lastScrapedAt }) {
  const timeAgo = lastScrapedAt ? formatTimeAgo(new Date(lastScrapedAt)) : null

  return (
    <header className="bg-slate-900 px-6 py-4 flex items-center justify-between flex-shrink-0">
      <div className="flex items-center gap-3">
        <BikeIcon />
        <span className="text-white font-semibold text-lg tracking-tight">BikeDeals</span>
        <span className="text-slate-500 text-xs font-medium bg-slate-800 px-2 py-0.5 rounded-full border border-slate-700">
          AU
        </span>
      </div>
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
