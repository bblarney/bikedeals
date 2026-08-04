// On the deals page the window itself doesn't scroll — the header and sidebar are
// pinned and only the grid column scrolls. Anything that used to call
// window.scrollTo goes through here so it targets whichever one is live.
export const MAIN_SCROLL_ID = 'main-scroll'

export function getMainScroller() {
  return document.getElementById(MAIN_SCROLL_ID)
}

export function scrollMainToTop() {
  const el = getMainScroller()
  if (el) el.scrollTo({ top: 0, behavior: 'smooth' })
  else window.scrollTo({ top: 0, behavior: 'smooth' })
}
