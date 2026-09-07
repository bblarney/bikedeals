import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { filterQueryKey, filterQueryParams } from '../lib/queries'

export function useFilters(params) {
  return useQuery({
    queryKey: filterQueryKey(params),
    queryFn: () => api.getFilters(filterQueryParams(params)),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  })
}
