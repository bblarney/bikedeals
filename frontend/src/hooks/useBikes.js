import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'

export function useBikeParams() {
  const [params, setParams] = useSearchParams()

  const get = (key, fallback = '') => params.get(key) ?? fallback
  const getAll = (key) => params.getAll(key)
  const getInt = (key, fallback = 0) => parseInt(params.get(key) ?? fallback, 10)

  function update(changes) {
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
    })
  }

  return {
    category: get('category'),
    city: get('city'),
    size: getAll('size'),
    vendor: get('vendor'),
    min_discount: getInt('min_discount', 0),
    q: get('q'),
    sort: get('sort', 'discount_desc'),
    offset: getInt('offset', 0),
    limit: 50,
    update,
  }
}

export function useBikes(bikeParams) {
  const { update: _update, ...queryParams } = bikeParams
  return useQuery({
    queryKey: ['bikes', queryParams],
    queryFn: () => api.getBikes(queryParams),
    placeholderData: (prev) => prev,
  })
}
