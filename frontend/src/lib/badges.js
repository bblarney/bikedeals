// Recency badges derived from scraped timestamps. Shared by BikeCard and the
// bike detail page so both agree on the 7-day window and precedence.
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000

export function recencyFlags(bike) {
  const cutoff = Date.now() - SEVEN_DAYS_MS
  const within = (ts) => ts && new Date(ts).getTime() > cutoff
  const isPriceDrop = within(bike.price_drop_at)
  const isNewDiscount = within(bike.discount_started_at)
  const isNew = within(bike.scraped_at)
  return {
    isPriceDrop,
    // Lower-priority badges suppressed when a higher one already shows.
    isNewDiscount: isNewDiscount && !isPriceDrop,
    isNew: isNew && !isPriceDrop && !isNewDiscount,
  }
}
