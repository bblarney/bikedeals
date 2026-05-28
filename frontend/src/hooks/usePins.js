import { useState, useCallback, useMemo, useEffect } from 'react'

const STORAGE_KEY = 'bikegrid_pins'

export function usePins() {
  const [pins, setPins] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) ?? [] }
    catch { return [] }
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pins))
  }, [pins])

  const pinnedIds = useMemo(() => new Set(pins.map(p => p.id)), [pins])

  const togglePin = useCallback((bike) => {
    setPins(prev =>
      prev.some(p => p.id === bike.id)
        ? prev.filter(p => p.id !== bike.id)
        : [bike, ...prev]
    )
  }, [])

  const clearPins = useCallback(() => setPins([]), [])

  return { pinnedBikes: pins, pinnedIds, togglePin, clearPins }
}
