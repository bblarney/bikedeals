import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useFilters() {
  return useQuery({
    queryKey: ['filters'],
    queryFn: api.getFilters,
    staleTime: 60 * 60 * 1000,
  })
}
