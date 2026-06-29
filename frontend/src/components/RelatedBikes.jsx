import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import BikeCard from './BikeCard'

// A horizontal rail of related deals (e.g. same brand or category). Pure
// internal-linking surface: keeps users browsing and feeds the crawler.
export default function RelatedBikes({ title, params, excludeId, pinnedIds = new Set(), onTogglePin = () => {} }) {
  const { data } = useQuery({
    queryKey: ['related', params],
    // Fetch a few extra so we still have a full row after dropping the current bike.
    queryFn: () => api.getBikes({ ...params, limit: 5, sort: 'discount_desc' }),
    staleTime: 5 * 60 * 1000,
  })

  const bikes = (data?.results ?? []).filter((b) => b.id !== excludeId).slice(0, 4)
  if (bikes.length === 0) return null

  return (
    <section className="mt-12">
      <h2 className="text-lg font-semibold text-slate-900 mb-4">{title}</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {bikes.map((bike) => (
          <BikeCard
            key={bike.id}
            bike={bike}
            isPinned={pinnedIds.has(bike.id)}
            onTogglePin={onTogglePin}
          />
        ))}
      </div>
    </section>
  )
}
