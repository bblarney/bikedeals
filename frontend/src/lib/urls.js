// Image and product URLs come from scraped third-party data. Only trust http(s)
// sources: defence in depth against javascript:, data: and other schemes ending
// up in an href or a src.
//
// One implementation rather than a copy per component, so a card, a table row
// and a detail page cannot disagree about what is safe to link to.
export function isHttpUrl(value) {
  if (!value) return false
  try {
    const u = new URL(value)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}
