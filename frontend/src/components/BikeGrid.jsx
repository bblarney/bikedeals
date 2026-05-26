import BikeCard from './BikeCard'

export default function BikeGrid({ bikes, isLoading, isError, total, params, onUpdate }) {
  const { offset, limit } = params
  const page = Math.floor(offset / limit) + 1
  const totalPages = total ? Math.ceil(total / limit) : 1

  if (isError) {
    return (
      <div className="text-center py-16 text-red-500">
        <p className="text-2xl mb-2">⚠️</p>
        <p className="font-medium">Failed to load deals</p>
        <p className="text-sm text-gray-500 mt-1">Check that the API is running and try again.</p>
      </div>
    )
  }

  if (!isLoading && bikes?.length === 0) {
    return (
      <div className="text-center py-16 text-gray-500">
        <p className="text-2xl mb-2">🔍</p>
        <p className="font-medium">No deals match your filters</p>
        <button
          onClick={() =>
            onUpdate({ category: '', city: '', size: [], vendor: '', min_discount: 0, q: '' })
          }
          className="mt-3 text-sm text-blue-600 hover:underline"
        >
          Clear all filters
        </button>
      </div>
    )
  }

  return (
    <div className="flex-1">
      {/* Results header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
        <p className="text-sm text-gray-600">
          {total != null ? (
            <>
              <span className="font-semibold text-gray-800">{total.toLocaleString()}</span> deals found
              {total > limit && (
                <> · page {page} of {totalPages}</>
              )}
            </>
          ) : (
            'Loading…'
          )}
        </p>
        <p className="text-xs text-gray-400">sorted by discount</p>
      </div>

      {/* Cards */}
      <div className={isLoading ? 'opacity-50' : ''}>
        {isLoading && !bikes?.length ? (
          <SkeletonList />
        ) : (
          bikes?.map((bike) => <BikeCard key={bike.id} bike={bike} />)
        )}
      </div>

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-center gap-2 py-4 border-t border-gray-200 bg-white">
          <button
            disabled={offset === 0}
            onClick={() => onUpdate({ offset: Math.max(0, offset - limit) })}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ← Prev
          </button>
          <span className="text-sm text-gray-600">
            {page} / {totalPages}
          </span>
          <button
            disabled={offset + limit >= total}
            onClick={() => onUpdate({ offset: offset + limit })}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
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
    <div className="animate-pulse">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
          <div className="w-16 h-16 bg-gray-200 rounded flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-3 bg-gray-200 rounded w-48" />
            <div className="h-2 bg-gray-200 rounded w-32" />
          </div>
          <div className="w-24 space-y-1 text-right">
            <div className="h-3 bg-gray-200 rounded" />
            <div className="h-2 bg-gray-200 rounded" />
          </div>
          <div className="w-20 h-8 bg-gray-200 rounded" />
        </div>
      ))}
    </div>
  )
}
