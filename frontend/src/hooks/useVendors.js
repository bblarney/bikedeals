import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

// One cache entry shared by /shops and every /shops/<slug>. The payload is one
// row per shop, so the detail page reads the whole list rather than an endpoint
// of its own, and gets its rank among its neighbours for free.
//
// staleTime matches useStats: these numbers only move when a scrape run lands.
export function useVendors() {
  return useQuery({
    queryKey: ['vendors'],
    queryFn: api.getVendors,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  })
}
