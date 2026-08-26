const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

// Error carrying the HTTP status so callers can branch on it (e.g. 409, 404)
// instead of brittle string-matching on the message.
export class ApiError extends Error {
  constructor(status, statusText) {
    super(`API ${status}: ${statusText}`)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, params = {}) {
  const url = new URL(BASE + path, window.location.origin)
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    if (Array.isArray(v)) v.forEach((i) => url.searchParams.append(k, i))
    else url.searchParams.set(k, v)
  })
  const res = await fetch(url.toString())
  if (!res.ok) throw new ApiError(res.status, res.statusText)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new ApiError(res.status, res.statusText)
  return res
}

export const api = {
  getBikes: (params) => request('/api/v1/bikes', params),
  getBike: (id) => request(`/api/v1/bikes/${encodeURIComponent(id)}`),
  getPriceHistory: (id) => request(`/api/v1/bikes/${encodeURIComponent(id)}/price-history`),
  getFilters: (params) => request('/api/v1/meta/filters', params),
  getStats: () => request('/api/v1/meta/stats'),
  getMarket: () => request('/api/v1/meta/market'),
  recordClick: (id) =>
    post(`/api/v1/bikes/${encodeURIComponent(id)}/click`).catch((err) => {
      if (import.meta.env.DEV) console.warn('click record failed', err)
    }),
  subscribe: (email) => post('/api/v1/subscribe', { email }),
  unsubscribe: (token) => post('/api/v1/unsubscribe', { token }),
}
