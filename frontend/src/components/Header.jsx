export default function Header({ total, lastScrapedAt }) {
  const timeAgo = lastScrapedAt ? formatTimeAgo(new Date(lastScrapedAt)) : null

  return (
    <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-xl font-bold text-gray-900">🚲 BikeDeals</span>
        <span className="text-xs text-gray-400 hidden sm:inline">AU</span>
      </div>
      {total != null && (
        <p className="text-sm text-gray-500">
          <span className="font-semibold text-gray-700">{total.toLocaleString()}</span> deals
          {timeAgo && <> · updated {timeAgo}</>}
        </p>
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
