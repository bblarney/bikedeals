import { REGIONS } from '../constants'

export default function LandingPage({ onUpdate }) {
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
        <BikeIcon />
        <span className="text-slate-900 font-bold text-2xl tracking-tight">BikeGrid</span>
        <span className="text-slate-400 text-sm font-medium bg-white px-2 py-0.5 rounded-full border border-slate-200">AU</span>
      </div>

      <h1 className="text-3xl font-bold text-slate-900 text-center mb-2">Find bike deals near you</h1>
      <p className="text-slate-500 text-center mb-10">Choose your region to see discounted bikes from local shops</p>

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

function BikeIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="5.5" cy="17.5" r="3.5" />
      <circle cx="18.5" cy="17.5" r="3.5" />
      <path d="M5.5 17.5L9 10h6l2 7.5" />
      <path d="M9 10l4-4 3 4" />
      <path d="M3 10h4" />
    </svg>
  )
}
