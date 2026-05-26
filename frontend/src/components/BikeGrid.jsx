import BikeCard from './BikeCard'

const SORT_LABELS = {
  discount_desc: 'biggest discount',
  price_asc: 'price: low → high',
  price_desc: 'price: high → low',
}

export default function BikeGrid({ bikes, isLoading, isError, total, params, onUpdate }) {
  const { offset, limit, sort } = params
  const page = Math.floor(offset / limit) + 1
  const totalPages = total ? Math.ceil(total / limit) : 1

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

  if (!isLoading && bikes?.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-24 text-slate-500">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mb-4">
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
        </svg>
        <p className="font-medium text-slate-700">No deals match your filters</p>
        <button
          onClick={() => onUpdate({ category: '', city: '', size: [], vendor: '', min_discount: 0, q: '' })}
          className="mt-3 text-sm text-blue-600 hover:text-blue-700 font-medium"
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
        <p className="text-sm text-slate-500">
          {total != null ? (
            <>
              <span className="font-semibold text-slate-800">{total.toLocaleString()}</span> deals
              {total > limit && <span className="text-slate-400"> · page {page} of {totalPages}</span>}
            </>
          ) : (
            <span className="text-slate-400">Loading…</span>
          )}
        </p>
        <p className="text-xs text-slate-400">sorted by {SORT_LABELS[sort] ?? sort}</p>
      </div>

      {/* Cards */}
      <div className={`flex-1 transition-opacity duration-150 ${isLoading ? 'opacity-40' : 'opacity-100'}`}>
        {isLoading && !bikes?.length ? <SkeletonList /> : bikes?.map((bike) => <BikeCard key={bike.id} bike={bike} />)}
      </div>

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-center gap-2 px-5 py-4 bg-white border-t border-slate-100">
          <button
            disabled={offset === 0}
            onClick={() => onUpdate({ offset: Math.max(0, offset - limit) })}
            className="px-3.5 py-1.5 text-sm font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            ← Prev
          </button>
          <span className="text-sm text-slate-400 tabular-nums px-2">
            {page} of {totalPages}
          </span>
          <button
            disabled={offset + limit >= total}
            onClick={() => onUpdate({ offset: offset + limit })}
            className="px-3.5 py-1.5 text-sm font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}

function SkeletonList() {
  return (
    <div className="divide-y divide-slate-100">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-5 py-3.5 animate-pulse">
          <div className="w-[72px] h-[72px] bg-slate-100 rounded-xl flex-shrink-0" />
          <div className="flex-1 space-y-2.5">
            <div className="h-3.5 bg-slate-100 rounded-full w-44" />
            <div className="h-2.5 bg-slate-100 rounded-full w-28" />
            <div className="h-2.5 bg-slate-100 rounded-full w-36" />
          </div>
          <div className="w-28 space-y-2 text-right">
            <div className="h-3 bg-slate-100 rounded-full ml-auto w-20" />
            <div className="h-5 bg-slate-100 rounded-full ml-auto w-16" />
          </div>
          <div className="w-20 h-8 bg-slate-100 rounded-lg" />
        </div>
      ))}
    </div>
  )
}
