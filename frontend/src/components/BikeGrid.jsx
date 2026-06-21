import BikeCard from './BikeCard'
import { DEFAULT_FILTERS } from '../constants'

const SORT_LABELS = {
  discount_desc: 'biggest discount',
  price_asc: 'price: low → high',
  price_desc: 'price: high → low',
  clicks_desc: 'most popular',
}

export default function BikeGrid({ bikes, isLoading, isFetching, isError, total, newToday, params, onUpdate, onSkuFilter = () => {}, pinnedBikes = [], pinnedIds = new Set(), onTogglePin = () => {}, onClearPins = () => {} }) {
  const { offset, limit, sort } = params
  const page = Math.floor(offset / limit) + 1
  const totalPages = total ? Math.ceil(total / limit) : 1
  const mainBikes = bikes?.filter(b => !pinnedIds.has(b.id)) ?? []

  if (isError) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-24 text-slate-500">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mb-4">
          <circle cx="12" cy="12" r="10" /><path d="M12 8v4m0 4h.01" />
        </svg>
        <p className="font-medium text-slate-700">Could not load deals</p>
        <p className="text-sm text-slate-400 mt-1">Check the API is running and try again.</p>
      </div>
    )
  }

  if (!isLoading && bikes?.length === 0 && pinnedBikes.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-24 text-slate-500">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mb-4">
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
        </svg>
        <p className="font-medium text-slate-700">No deals match your filters</p>
        <button
          onClick={() => onUpdate(DEFAULT_FILTERS)}
          className="mt-3 text-sm text-orange-600 hover:text-orange-700 font-medium"
        >
          Clear all filters
        </button>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Results bar */}
      <div className="flex items-center justify-between px-5 py-2.5 bg-white border-b border-slate-100">
        <div className="flex items-center gap-2">
          {isFetching && <Spinner />}
          <p className="text-sm text-slate-500">
            {total != null ? (
              <>
                <span className="font-semibold text-slate-800">{total.toLocaleString()}</span> deals
              </>
            ) : (
              <span className="text-slate-400">Loading…</span>
            )}
          </p>
          {newToday > 0 && (
            <span className="text-xs font-medium text-orange-700 bg-orange-50 px-2 py-0.5 rounded-full">
              {newToday} new today
            </span>
          )}
          {total > limit && (
            <>
              <button
                disabled={offset === 0}
                onClick={() => { onUpdate({ offset: Math.max(0, offset - limit) }); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                className="px-2.5 py-1 text-xs font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                ← Prev
              </button>
              <span className="text-xs text-slate-400 tabular-nums">{page} of {totalPages}</span>
              <button
                disabled={offset + limit >= total}
                onClick={() => { onUpdate({ offset: offset + limit }); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                className="px-2.5 py-1 text-xs font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                Next →
              </button>
            </>
          )}
          {pinnedBikes.length > 0 && (
            <button
              onClick={onClearPins}
              className="px-2.5 py-1 text-xs font-medium text-orange-700 border border-orange-200 rounded-lg hover:bg-orange-50 transition-colors"
            >
              Clear saved ({pinnedBikes.length})
            </button>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-400">Sort by</span>
          <select
            value={sort}
            onChange={(e) => onUpdate({ sort: e.target.value })}
            className="text-xs text-slate-600 border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition appearance-none cursor-pointer"
          >
            {Object.entries(SORT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Cards */}
      <div className={`flex-1 transition-opacity duration-150 ${isLoading ? 'opacity-40' : 'opacity-100'}`}>
        {isLoading && !bikes?.length ? (
          <SkeletonGrid />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-4 p-4">
            {pinnedBikes.map(bike => (
              <BikeCard key={`pin-${bike.id}`} bike={bike} isPinned={true} onTogglePin={onTogglePin} onSkuFilter={onSkuFilter} />
            ))}
            {mainBikes.map(bike => (
              <BikeCard key={bike.id} bike={bike} isPinned={false} onTogglePin={onTogglePin} onSkuFilter={onSkuFilter} />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-center gap-2 px-5 py-4 bg-white border-t border-slate-100">
          <button
            disabled={offset === 0}
            onClick={() => { onUpdate({ offset: Math.max(0, offset - limit) }); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
            className="px-3.5 py-1.5 text-sm font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            ← Prev
          </button>
          <span className="text-sm text-slate-400 tabular-nums px-2">
            {page} of {totalPages}
          </span>
          <button
            disabled={offset + limit >= total}
            onClick={() => { onUpdate({ offset: offset + limit }); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
            className="px-3.5 py-1.5 text-sm font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin text-orange-500" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M12 2a10 10 0 0 1 10 10" />
    </svg>
  )
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-4 p-4">
      {Array.from({ length: 12 }).map((_, i) => (
        <div key={i} className="bg-white rounded-xl border border-slate-100 overflow-hidden animate-pulse flex flex-col">
          <div className="aspect-square bg-slate-100" />
          <div className="p-3 flex flex-col gap-2">
            <div className="h-3 bg-slate-100 rounded-full w-16" />
            <div className="h-3.5 bg-slate-100 rounded-full w-full" />
            <div className="h-3.5 bg-slate-100 rounded-full w-4/5" />
            <div className="h-2.5 bg-slate-100 rounded-full w-24 mt-1" />
            <div className="mt-3 h-4 bg-slate-100 rounded-full w-20" />
            <div className="h-8 bg-slate-100 rounded-lg mt-1" />
          </div>
        </div>
      ))}
    </div>
  )
}
