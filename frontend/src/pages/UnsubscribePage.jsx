import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { api } from '../api/client'
import { canonicalFor } from '../seo'

export default function UnsubscribePage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState('loading') // loading | success | notfound | error | missing

  useEffect(() => {
    if (!token) {
      setStatus('missing')
      return
    }
    api.unsubscribe(token)
      .then(() => setStatus('success'))
      .catch((err) => setStatus(err.message === '404' ? 'notfound' : 'error'))
  }, [token])

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <title>Unsubscribe — BikeGrid</title>
      <link rel="canonical" href={canonicalFor('/unsubscribe')} />

      <h1 className="text-2xl font-semibold text-slate-900 mb-6">Unsubscribe</h1>

      {status === 'loading' && (
        <p className="text-slate-500">Removing your email…</p>
      )}

      {status === 'success' && (
        <>
          <p className="text-slate-700 leading-relaxed mb-4">
            You've been unsubscribed. You won't receive any further emails from BikeGrid.
          </p>
          <Link to="/" className="text-blue-600 hover:underline text-sm">Back to BikeGrid</Link>
        </>
      )}

      {status === 'notfound' && (
        <p className="text-slate-500 leading-relaxed">
          This unsubscribe link is invalid or has already been used.
        </p>
      )}

      {status === 'missing' && (
        <p className="text-slate-500 leading-relaxed">
          No unsubscribe token found. Please use the link from your email.
        </p>
      )}

      {status === 'error' && (
        <p className="text-red-600 leading-relaxed">
          Something went wrong. Please try again or{' '}
          <Link to="/contact" className="underline">contact us</Link>.
        </p>
      )}
    </div>
  )
}
