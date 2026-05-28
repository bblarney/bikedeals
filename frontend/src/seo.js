const FALLBACK = 'https://bikegrid.com.au'

export function canonicalFor(path = '/') {
  const base = import.meta.env.VITE_PUBLIC_URL || FALLBACK
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${base.replace(/\/$/, '')}${normalized}`
}
