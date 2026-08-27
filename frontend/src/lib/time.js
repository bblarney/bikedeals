// Spelled out rather than left to toLocaleDateString, which is not the same
// function everywhere: Node's ICU renders en-AU `month: 'short'` as "20 June"
// where a browser gives "20 Jun". These dates are rendered in both, because
// scripts/prerender.js runs the pages through Node, so the locale API would
// ship two spellings of the same date to the same page.
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// Short absolute date, e.g. "20 Jun", with the year once it stops being obvious.
export function formatShortDate(date) {
  const month = MONTHS[date.getMonth()]
  const year = date.getFullYear()
  const suffix = year === new Date().getFullYear() ? '' : ` ${year}`
  return `${date.getDate()} ${month}${suffix}`
}

// When something was last true, in the words a person would use: "today",
// "yesterday", or a date.
//
// This replaced a relative "4h ago" on every freshness signal on the site.
// Relative time is precise and useless here: the scrape runs once a day, so
// "17h ago" is the same fact as "22h ago" dressed up as a difference, and it
// changes every time you look at the page without the data having changed.
// Whether the number in front of you is from today or from three weeks ago is
// the only distinction a buyer needs, and it is the one "today" makes.
//
// Calendar days, not elapsed hours: 11pm last night is yesterday, not "2h ago".
export function formatDayLabel(date) {
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOfDay(new Date()) - startOfDay(date)) / 86400000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  return formatShortDate(date)
}
