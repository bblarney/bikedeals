import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

// One request feeds every chart on /trends, so the whole page shares a cache
// entry and a loading state. The API only changes after the nightly scrape run
// and sends max-age=3600 to match, hence the long staleTime.
export function useMarket() {
  return useQuery({
    queryKey: ['market'],
    queryFn: api.getMarket,
    staleTime: 60 * 60 * 1000,
    gcTime: 2 * 60 * 60 * 1000,
  })
}
