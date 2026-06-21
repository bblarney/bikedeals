import { useEffect, useRef, useState } from 'react'

export default function MultiSelectDropdown({ label, options, selected, onChange, searchable = false }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const ref = useRef(null)
  const buttonRef = useRef(null)
  const searchRef = useRef(null)

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    function handleKey(e) {
      if (e.key === 'Escape' && open) {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  useEffect(() => {
    if (open && searchable) searchRef.current?.focus()
    if (!open) setQuery('')
  }, [open, searchable])

  function toggle(val) {
    onChange(selected.includes(val) ? selected.filter((x) => x !== val) : [...selected, val])
  }

  const summary = selected.length === 0 ? `All ${label.toLowerCase()}` : selected.join(', ')
  const hasSelection = selected.length > 0
  const visible = searchable && query
    ? options.filter((o) => o.toLowerCase().includes(query.toLowerCase()))
    : options

  const allVisibleSelected = visible.length > 0 && visible.every((o) => selected.includes(o))
  const someVisibleSelected = visible.some((o) => selected.includes(o))

  function toggleAll() {
    if (allVisibleSelected) {
      onChange(selected.filter((x) => !visible.includes(x)))
    } else {
      const toAdd = visible.filter((o) => !selected.includes(o))
      onChange([...selected, ...toAdd])
    }
  }

  const selectAllRef = useRef(null)
  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someVisibleSelected && !allVisibleSelected
    }
  })

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        ref={buttonRef}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={`w-full flex items-center justify-between gap-2 border rounded-lg px-3 py-2 text-sm text-left transition ${
          open
            ? 'border-orange-500 ring-2 ring-orange-500/20'
            : 'border-slate-200 hover:border-slate-300'
        } ${hasSelection ? 'bg-orange-50 border-orange-300 text-orange-700 font-medium' : 'bg-white text-slate-700'}`}
      >
        <span className="truncate">{summary}</span>
        <svg
          className={`w-4 h-4 flex-shrink-0 text-slate-400 transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
          viewBox="0 0 20 20" fill="currentColor"
        >
          <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden">
          {searchable && (
            <div className="px-2 pt-2 pb-1 border-b border-slate-100">
              <input
                ref={searchRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={`Search ${label.toLowerCase()}…`}
                className="w-full border border-slate-200 rounded-md px-2.5 py-1.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
              />
            </div>
          )}
          <div className="py-1 max-h-52 overflow-y-auto">
            {visible.length === 0 ? (
              <p className="px-3 py-2 text-sm text-slate-400">No matches</p>
            ) : (
              <>
                <label className="flex items-center gap-2.5 px-3 py-2 text-sm cursor-pointer border-b border-slate-100 text-slate-500 hover:bg-slate-50">
                  <input
                    ref={selectAllRef}
                    type="checkbox"
                    checked={allVisibleSelected}
                    onChange={toggleAll}
                    className="accent-orange-600 w-3.5 h-3.5"
                  />
                  <span>Select all{query ? ' matches' : ''}</span>
                </label>
                {visible.map((opt) => {
                  const checked = selected.includes(opt)
                  return (
                    <label
                      key={opt}
                      className={`flex items-center gap-2.5 px-3 py-2 text-sm cursor-pointer transition-colors ${
                        checked ? 'bg-orange-50 text-orange-700' : 'text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(opt)}
                        className="accent-orange-600 w-3.5 h-3.5"
                      />
                      <span className={checked ? 'font-medium' : ''}>{opt}</span>
                    </label>
                  )
                })}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
