import { useState, useEffect, useRef } from 'react'
import { useStats } from '../hooks/useStats'

function buildItems(data) {
  if (!data) return []
  return [
    { value: data.new_today,                    label: 'new bikes today' },
    { value: data.shops_tracked,                label: 'shops tracked' },
    { value: `${data.biggest_discount}%`,       label: 'biggest discount right now' },
    { value: `${data.avg_discount}%`,           label: 'average discount' },
  ]
}

const CYCLE_MS = 3500

export default function StatsBanner() {
  const { data, isLoading, isError } = useStats()
  const items = buildItems(data)
  const [activeIndex, setActiveIndex] = useState(0)
  const [visible, setVisible] = useState(true)
  const timerRef = useRef(null)

  useEffect(() => {
    if (items.length < 2) return
    timerRef.current = setInterval(() => {
      setVisible(false)
      setTimeout(() => {
        setActiveIndex(i => (i + 1) % items.length)
        setVisible(true)
      }, 300)
    }, CYCLE_MS)
    return () => clearInterval(timerRef.current)
  }, [items.length])

  if (isLoading) {
    return (
      <div className="h-8 bg-slate-800 border-b border-slate-700 flex items-center justify-center flex-shrink-0">
        <div className="h-3 w-48 bg-slate-700 rounded animate-pulse" />
      </div>
    )
  }

  if (isError || items.length === 0) return null

  const item = items[activeIndex]

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Site statistics"
      className="h-8 bg-slate-800 border-b border-slate-700 flex items-center justify-center overflow-hidden flex-shrink-0"
    >
      <p
        className="text-xs text-slate-300 tracking-wide transition-opacity duration-300"
        style={{ opacity: visible ? 1 : 0 }}
      >
        <span className="font-semibold text-white">{item.value}</span>
        {' '}
        <span>{item.label}</span>
      </p>
    </div>
  )
}
