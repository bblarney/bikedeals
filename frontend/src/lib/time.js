// Relative "x ago" for freshness signals (e.g. last scrape, recent price drop).
export function formatTimeAgo(date) {
  const diff = (Date.now() - date.getTime()) / 1000
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

// Short absolute date, e.g. "20 Jun". Used for "on sale since" copy.
export function formatShortDate(date) {
  return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })
}
