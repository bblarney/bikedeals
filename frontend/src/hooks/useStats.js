import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: api.getStats,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    retry: false,
  })
}
