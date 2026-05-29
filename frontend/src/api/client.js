const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

async function request(path, params = {}) {
  const url = new URL(BASE + path, window.location.origin)
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    if (Array.isArray(v)) v.forEach((i) => url.searchParams.append(k, i))
    else url.searchParams.set(k, v)
  })
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export const api = {
  getBikes: (params) => request('/api/v1/bikes', params),
  getFilters: (params) => request('/api/v1/meta/filters', params),
  getStats: () => request('/api/v1/meta/stats'),
  recordClick: (id) =>
    fetch(`${BASE}/api/v1/bikes/${id}/click`, { method: 'POST' }).catch((err) =>
      console.warn('click record failed', err),
    ),
  subscribe: (email) =>
    fetch(`${BASE}/api/v1/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    }).then((r) => { if (!r.ok) throw new Error(r.status) }),
  unsubscribe: (token) =>
    fetch(`${BASE}/api/v1/unsubscribe/${encodeURIComponent(token)}`).then(
      (r) => { if (!r.ok) throw new Error(r.status) },
    ),
}
