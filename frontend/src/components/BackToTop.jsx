import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { MAIN_SCROLL_ID, scrollMainToTop } from '../lib/scroll'

export default function BackToTop() {
  const [visible, setVisible] = useState(false)
  const { pathname } = useLocation()

  useEffect(() => {
    // Scroll events don't bubble, so listen in the capture phase — that catches both
    // the document and the deals page's inner scroll column without holding a ref to
    // an element that gets swapped out when the layout changes.
    const onScroll = (e) => {
      const el = e.target === document ? document.documentElement : e.target
      if (el !== document.documentElement && el.id !== MAIN_SCROLL_ID) return
      setVisible(el.scrollTop > 300)
    }
    document.addEventListener('scroll', onScroll, { capture: true, passive: true })
    return () => document.removeEventListener('scroll', onScroll, { capture: true })
  }, [])

  // A new route starts at the top, and its scroller may be a different element.
  useEffect(() => setVisible(false), [pathname])

  return (
    <button
      onClick={scrollMainToTop}
      aria-label="Back to top"
      className={`fixed bottom-6 right-6 z-50 w-10 h-10 flex items-center justify-center bg-orange-600 hover:bg-orange-700 text-white rounded-full shadow-lg transition-all duration-200 ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'
      }`}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 12V4M4 7l4-4 4 4" />
      </svg>
    </button>
  )
}
