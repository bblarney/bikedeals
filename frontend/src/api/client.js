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
  recordClick: (id) =>
    fetch(`${BASE}/api/v1/bikes/${id}/click`, { method: 'POST' }).catch((err) =>
      console.warn('click record failed', err),
    ),
}
