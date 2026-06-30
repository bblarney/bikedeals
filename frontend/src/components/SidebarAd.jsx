import { useEffect, useRef } from 'react'

// Manual AdSense display unit. The loader script lives once in index.html;
// here we just push the slot when the <ins> mounts. The ref guard stops React
// StrictMode's double-effect (dev) from pushing twice and throwing
// "All 'ins' elements in the DOM with class=adsbygoogle already have ads".
export default function SidebarAd() {
  const pushed = useRef(false)

  useEffect(() => {
    if (pushed.current) return
    pushed.current = true
    try {
      ;(window.adsbygoogle = window.adsbygoogle || []).push({})
    } catch {
      /* adsbygoogle not ready (e.g. blocked / dev localhost) — noop */
    }
  }, [])

  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">Advertisement</p>
      <ins
        className="adsbygoogle"
        style={{ display: 'block' }}
        data-ad-client="ca-pub-1705476604410175"
        data-ad-slot="9484872263"
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </div>
  )
}
