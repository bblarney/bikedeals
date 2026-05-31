import { useState, useMemo } from 'react'
import { REGIONS, SIZE_ORDER } from '../constants'
import { useFilters } from '../hooks/useFilters'

const selectClass =
  'w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition cursor-pointer'

export default function LandingPage({ onUpdate }) {
  const [selectedCategory, setSelectedCategory] = useState('')
  const [selectedSize, setSelectedSize] = useState('')
  const [selectedCity, setSelectedCity] = useState('')

  const { data: filtersData } = useFilters({})

  const sizes = useMemo(() => {
    if (!filtersData?.sizes) return []
    return [...filtersData.sizes].sort((a, b) => {
      const ai = SIZE_ORDER.indexOf(a)
      const bi = SIZE_ORDER.indexOf(b)
      if (ai !== -1 && bi !== -1) return ai - bi
      if (ai !== -1) return -1
      if (bi !== -1) return 1
      return a.localeCompare(b)
    })
  }, [filtersData])

  const cities = filtersData?.cities ?? []
  const categories = filtersData?.categories ?? []

  function handleSearch() {
    const changes = {}
    if (selectedCategory) changes.category = [selectedCategory]
    if (selectedSize)     changes.size     = [selectedSize]
    if (selectedCity) {
      changes.city = [selectedCity]
      const region = REGIONS.find(r => r.cities.includes(selectedCity))
      localStorage.setItem('bikegrid_region', region ? region.name : '__all__')
    } else {
      localStorage.setItem('bikegrid_region', '__all__')
    }
    onUpdate(changes)
  }

  function pickRegion(region) {
    localStorage.setItem('bikegrid_region', region.name)
    onUpdate({ city: region.cities })
  }

  function pickAll() {
    localStorage.setItem('bikegrid_region', '__all__')
    onUpdate({})
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-slate-50 px-6 py-16">
      {/* Logo */}
      <div className="flex items-center gap-3 mb-10">
        <img src="/logos/bikegrid/bikegrid-black.png" alt="BikeGrid" className="h-14 w-auto" />
        <span className="text-slate-400 text-sm font-medium bg-white px-2 py-0.5 rounded-full border border-slate-200">AU</span>
      </div>

      <h1 className="text-3xl font-bold text-slate-900 text-center mb-10">Find bike deals near you</h1>

      {/* Filter form */}
      <div className="bg-white border border-slate-200 rounded-2xl px-8 py-7 w-full max-w-lg shadow-sm">
        <p className="text-sm font-medium text-slate-700 mb-4">I'm looking for...</p>
        <div className="space-y-3">
          {[
            { label: 'Category', value: selectedCategory, onChange: setSelectedCategory, options: categories },
            { label: 'Size',     value: selectedSize,     onChange: setSelectedSize,     options: sizes     },
            { label: 'Near',     value: selectedCity,     onChange: setSelectedCity,     options: cities    },
          ].map(({ label, value, onChange, options }) => (
            <div key={label} className="grid grid-cols-[4rem_1fr] items-center gap-4">
              <span className="text-sm text-slate-500">{label}</span>
              <select value={value} onChange={e => onChange(e.target.value)} className={selectClass}>
                <option value="">I don't know</option>
                {options.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
          ))}
        </div>

        <button
          onClick={handleSearch}
          className="mt-6 w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl py-2.5 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Search
        </button>
      </div>

      {/* Divider */}
      <div className="flex items-center gap-3 w-full max-w-lg my-8">
        <div className="flex-1 h-px bg-slate-200" />
        <span className="text-xs text-slate-400 font-medium">or choose a region</span>
        <div className="flex-1 h-px bg-slate-200" />
      </div>

      {/* Region cards */}
      <div className="grid grid-cols-2 gap-4 w-full max-w-lg">
        {REGIONS.map((region) => (
          <button
            key={region.name}
            onClick={() => pickRegion(region)}
            className="group bg-white border border-slate-200 rounded-2xl p-6 text-left hover:border-blue-400 hover:shadow-md transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-2xl font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                {region.abbr}
              </span>
              <svg className="text-slate-300 group-hover:text-blue-400 transition-colors" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 10h12M10 4l6 6-6 6" />
              </svg>
            </div>
            <p className="text-sm font-medium text-slate-700 mb-1">{region.name}</p>
            <p className="text-xs text-slate-400 leading-relaxed">{region.cities.join(', ')}</p>
          </button>
        ))}
      </div>

      <button
        onClick={pickAll}
        className="mt-8 text-sm text-slate-400 hover:text-blue-600 transition-colors"
      >
        Show all of Australia →
      </button>
    </div>
  )
}
