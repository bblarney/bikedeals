import { useEffect, useLayoutEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { getMainScroller } from '../lib/scroll'

// React Router keeps the scroll position across client-side navigations, so
// following a link from halfway down one guide drops you halfway down the next.
// This resets it, except when the target carries a hash, where the point of the
// link is to land on a section (e.g. /guides/electric-bikes#e-mtb) and Router
// does not scroll to it on its own.
//
// Layout effect rather than effect so the reset happens before paint; falls back
// to useEffect during the build-time prerender, where neither runs but
// useLayoutEffect would warn.
const useIsomorphicLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect

export default function ScrollToTop() {
  const { pathname, hash } = useLocation()

  useIsomorphicLayoutEffect(() => {
    if (hash) {
      const target = document.getElementById(hash.slice(1))
      if (target) {
        target.scrollIntoView()
        return
      }
    }
    // Instant, not smooth: this is a new page arriving, not a jump within one.
    // Both scrollers are reset because the deals route scrolls an inner column
    // instead of the document (see lib/scroll.js).
    window.scrollTo(0, 0)
    getMainScroller()?.scrollTo(0, 0)
  }, [pathname, hash])

  return null
}
