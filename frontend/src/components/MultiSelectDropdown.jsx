import { useEffect, useRef, useState } from 'react'

export default function MultiSelectDropdown({ label, options, selected, onChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function toggle(val) {
    onChange(selected.includes(val) ? selected.filter((x) => x !== val) : [...selected, val])
  }

  const summary = selected.length === 0 ? `All ${label.toLowerCase()}` : selected.join(', ')
  const hasSelection = selected.length > 0

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`w-full flex items-center justify-between gap-2 border rounded-lg px-3 py-2 text-sm text-left transition ${
          open
            ? 'border-blue-500 ring-2 ring-blue-500/20'
            : 'border-slate-200 hover:border-slate-300'
        } ${hasSelection ? 'bg-blue-50 border-blue-300 text-blue-700 font-medium' : 'bg-white text-slate-700'}`}
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
          <div className="py-1 max-h-52 overflow-y-auto">
            {options.map((opt) => {
              const checked = selected.includes(opt)
              return (
                <label
                  key={opt}
                  className={`flex items-center gap-2.5 px-3 py-2 text-sm cursor-pointer transition-colors ${
                    checked ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(opt)}
                    className="accent-blue-600 w-3.5 h-3.5"
                  />
                  <span className={checked ? 'font-medium' : ''}>{opt}</span>
                </label>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
