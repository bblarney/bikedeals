// Recency badges derived from scraped timestamps. Shared by BikeCard and the
// bike detail page so both agree on the 7-day window and precedence.
import { money } from './money'
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

// The cross-shop line, shared by the card and the table so the two views tell
// the same story about the same bike.
//
// The count alone was trivia: three shops stock it, so what. The floor price is
// the reason to open the comparison, so it leads whenever there is one to show.
// Three cases, and each has to be true:
//
//   - no floor price: the API predates sku_min_price (the frontend and the API
//     deploy separately), so claim nothing about price and keep the count.
//   - a cheaper shop: name the floor.
//   - no cheaper shop: "none cheaper" rather than "cheapest", because the floor
//     includes this listing and a tie is not a win.
//
// Compared in rounded dollars, because rounded dollars are what the card
// prints: a 40c gap must not advertise a "cheaper" price that reads identically
// to the one directly above it.
//
// Returns null when there is nothing to compare, else { text, cheaper }, where
// `cheaper` says a shop is undercutting this listing. The table colours on it;
// the card does not need to, because the price is already in the sentence.
export function crossShopLine(bike) {
  const { product_key, sku_vendor_count = 0, sku_min_price, price_sale } = bike
  if (!product_key || sku_vendor_count < 2) return null

  const shops = `${sku_vendor_count} shops`
  if (!(sku_min_price > 0)) return { text: `Compare ${shops}`, cheaper: false }
  if (Math.round(sku_min_price) < Math.round(price_sale)) {
    return { text: `${shops}, from ${money(sku_min_price)}`, cheaper: true }
  }
  return { text: `${shops}, none cheaper`, cheaper: false }
}
