import BikeCard from './BikeCard'
import BikeTable from './BikeTable'
import ResultsToolbar from './ResultsToolbar'
import { DEFAULT_FILTERS } from '../constants'
import { scrollMainToTop } from '../lib/scroll'

export default function BikeGrid({
  bikes, isLoading, isFetching, isError, total, shopCount, lastScrapedAt, newToday,
  params, onUpdate, pinnedBikes = [], pinnedIds = new Set(), onTogglePin = () => {}, onClearPins = () => {},
}) {
  const { offset, limit, view } = params
  const page = Math.floor(offset / limit) + 1
  const totalPages = total ? Math.ceil(total / limit) : 1
  const mainBikes = bikes?.filter(b => !pinnedIds.has(b.id)) ?? []
  // Saved bikes ride at the top of the grid so a comparison survives a filter
  // change. In the table they would break the column sort, so they do not.
  const rows = view === 'table' ? mainBikes : [...pinnedBikes, ...mainBikes]

  if (isError) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-24 text-slate-500">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mb-4">
          <circle cx="12" cy="12" r="10" /><path d="M12 8v4m0 4h.01" />
        </svg>
        <p className="font-medium text-slate-700">Could not load bikes</p>
        <p className="text-sm text-slate-400 mt-1">Check the API is running and try again.</p>
      </div>
    )
  }

  if (!isLoading && bikes?.length === 0 && pinnedBikes.length === 0) {
    return (
      <div className="flex-1 flex flex-col">
        <ResultsToolbar
          total={total} shopCount={shopCount} lastScrapedAt={lastScrapedAt} newToday={newToday}
          isFetching={isFetching} params={params} onUpdate={onUpdate}
          savedCount={pinnedBikes.length} onClearSaved={onClearPins}
        />
        <div className="flex-1 flex flex-col items-center justify-center py-24 text-slate-500">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mb-4">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
          </svg>
          <p className="font-medium text-slate-700">No bikes match your filters</p>
          <button
            onClick={() => onUpdate(DEFAULT_FILTERS)}
            className="mt-3 text-sm text-orange-600 hover:text-orange-700 font-medium"
          >
            Clear all filters
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col">
      <ResultsToolbar
        total={total} shopCount={shopCount} lastScrapedAt={lastScrapedAt} newToday={newToday}
        isFetching={isFetching} params={params} onUpdate={onUpdate}
        savedCount={pinnedBikes.length} onClearSaved={onClearPins}
      />

      <div className={`flex-1 transition-opacity duration-150 ${isLoading ? 'opacity-40' : 'opacity-100'}`}>
        {isLoading && !bikes?.length ? (
          <SkeletonGrid />
        ) : view === 'table' ? (
          <BikeTable
            bikes={rows}
            params={params}
            onUpdate={onUpdate}
            pinnedIds={pinnedIds}
            onTogglePin={onTogglePin}
          />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3 p-3">
            {rows.map(bike => (
              <BikeCard
                key={bike.id}
                bike={bike}
                isPinned={pinnedIds.has(bike.id)}
                onTogglePin={onTogglePin}
              />
            ))}
          </div>
        )}
      </div>

      {total > limit && (
        <div className="flex items-center justify-center gap-2 px-5 py-4 bg-white border-t border-slate-100">
          <PageButton
            disabled={offset === 0}
            onClick={() => { onUpdate({ offset: Math.max(0, offset - limit) }); scrollMainToTop() }}
          >
            &larr; Prev
          </PageButton>
          <span className="tabular-nums text-sm text-slate-400 px-2">
            {page} of {totalPages}
          </span>
          <PageButton
            disabled={offset + limit >= total}
            onClick={() => { onUpdate({ offset: offset + limit }); scrollMainToTop() }}
          >
            Next &rarr;
          </PageButton>
        </div>
      )}
    </div>
  )
}

function PageButton({ disabled, onClick, children }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="px-3.5 py-1.5 text-sm font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
    >
      {children}
    </button>
  )
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3 p-3">
      {Array.from({ length: 12 }).map((_, i) => (
        <div key={i} className="bg-white rounded-xl border border-slate-200 overflow-hidden animate-pulse flex flex-col">
          <div className="aspect-[5/4] bg-slate-100" />
          <div className="p-3 flex flex-col gap-2">
            <div className="h-2.5 bg-slate-100 rounded-full w-16" />
            <div className="h-3.5 bg-slate-100 rounded-full w-full" />
            <div className="h-3.5 bg-slate-100 rounded-full w-4/5" />
            <div className="mt-1 h-4 bg-slate-100 rounded-full w-24" />
            <div className="h-2.5 bg-slate-100 rounded-full w-20" />
            <div className="h-8 bg-slate-100 rounded-lg mt-1" />
          </div>
        </div>
      ))}
    </div>
  )
}
