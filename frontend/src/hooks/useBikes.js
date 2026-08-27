import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'

// `lockedCategory` comes from the route: /road-bikes is the category, so it is
// not in the query string and the sidebar does not offer to change it. The
// category bar switches routes instead.
export function useBikeParams(lockedCategory = null) {
  const [params, setParams] = useSearchParams()

  const get = (key, fallback = '') => params.get(key) ?? fallback
  const getAll = (key) => params.getAll(key)
  const getInt = (key, fallback = 0) => parseInt(params.get(key) ?? fallback, 10)

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
    category: lockedCategory ? [lockedCategory] : getAll('category'),
    city: getAll('city'),
    size: getAll('size'),
    vendor: getAll('vendor'),
    brand: getAll('brand'),
    frame_material: getAll('frame_material'),
    drivetrain_groupset: getAll('drivetrain_groupset'),
    min_discount: getInt('min_discount', 0),
    min_price: get('min_price'),
    max_price: get('max_price'),
    q: get('q'),
    added_since: get('added_since'),
    sort: get('sort', 'discount_desc'),
    // Grid or table. A URL preference rather than component state, so a
    // comparison view survives a refresh and can be linked to.
    view: get('view', 'grid') === 'table' ? 'table' : 'grid',
    offset: getInt('offset', 0),
    limit: 48,
    sku: get('sku'),
    product_key: get('product_key'),
    lockedCategory,
    update,
    filterByProduct,
  }
}

export function useBikes(bikeParams) {
  const {
    update: _update,
    filterByProduct: _filterByProduct,
    lockedCategory: _lockedCategory,
    view: _view,
    ...queryParams
  } = bikeParams
  return useQuery({
    queryKey: ['bikes', queryParams],
    queryFn: () => api.getBikes(queryParams),
    placeholderData: (prev) => prev,
  })
}
