import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useFilters(params) {
  const { category, city, size, vendor, brand, frame_material, drivetrain_groupset, min_discount, min_price, max_price, q, added_since } = params ?? {}
  const filterParams = { category, city, size, vendor, brand, frame_material, drivetrain_groupset, min_discount, min_price, max_price, q, added_since }

  return useQuery({
    queryKey: ['filters', filterParams],
    queryFn: () => api.getFilters(filterParams),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  })
}
