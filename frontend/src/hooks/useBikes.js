import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { bikeQueryKey, bikeQueryParams, readBikeParams } from '../lib/queries'

// The feed's parameters live in the URL. Reading them is lib/queries.js's job,
// shared with the prerender; this hook adds the two ways of writing them.
export function useBikeParams(lockedCategory = null) {
  const [params, setParams] = useSearchParams()

  function update(changes, { replace = false } = {}) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      Object.entries(changes).forEach(([k, v]) => {
        next.delete(k)
        if (Array.isArray(v)) v.forEach((i) => next.append(k, i))
        else if (v !== undefined && v !== null && v !== '' && v !== 0) next.set(k, v)
      })
      // reset offset when any filter changes (unless offset itself is the change)
      if (!('offset' in changes)) next.delete('offset')
      return next
    }, { replace })
  }

  // Narrow the feed to one product across every shop. Keyed on product_key, not
  // sku: shop SKUs collide across brands, so ?sku= pulled in unrelated bikes.
  function filterByProduct(product_key) {
    setParams(new URLSearchParams({ product_key }))
  }

  return {
    ...readBikeParams(params, lockedCategory),
    update,
    filterByProduct,
  }
}

export function useBikes(bikeParams) {
  return useQuery({
    queryKey: bikeQueryKey(bikeParams),
    queryFn: () => api.getBikes(bikeQueryParams(bikeParams)),
    placeholderData: (prev) => prev,
  })
}
