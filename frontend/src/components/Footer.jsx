import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

const CATEGORIES = [
  { label: 'Road bikes', to: '/?category=Road' },
  { label: 'Mountain bikes', to: '/?category=Mountain' },
  { label: 'Gravel bikes', to: '/?category=Gravel' },
  { label: 'E-Bikes', to: '/?category=E-Bike' },
  { label: 'Commuter bikes', to: '/?category=Commuter' },
]

const COMPANY_LINKS = [
  { label: 'About', to: '/about' },
  { label: 'Contact', to: '/contact' },
  { label: 'Terms of Use', to: '/terms' },
  { label: 'Privacy Policy', to: '/privacy' },
  { label: 'Sitemap', to: '/sitemap' },
]

export default function Footer() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('idle') // idle | loading | success | error

  async function handleSubscribe(e) {
    e.preventDefault()
    if (!email) return
    setStatus('loading')
    try {
      await api.subscribe(email)
      setStatus('success')
      setEmail('')
    } catch (err) {
      setStatus(err.status === 409 ? 'duplicate' : 'error')
    }
  }

  return (
    <footer className="bg-navy-900 mt-auto">
      <div className="max-w-7xl mx-auto px-6 py-10">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <img src="/logos/bikegrid/bikegrid_white.png" alt="BikeGrid" className="h-12 w-auto" />
            <p className="mt-2 text-slate-400 text-sm leading-relaxed">
              Daily deals from local Australian bike shops — in one place.
            </p>
          </div>

          <nav aria-label="Browse by category">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Explore
            </p>
            <ul className="space-y-2">
              {CATEGORIES.map(({ label, to }) => (
                <li key={to}>
                  <Link
                    to={to}
                    className="text-slate-400 hover:text-white text-sm transition-colors"
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Company links">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Company
            </p>
            <ul className="space-y-2">
              {COMPANY_LINKS.map(({ label, to }) => (
                <li key={to}>
                  <Link
                    to={to}
                    className="text-slate-400 hover:text-white text-sm transition-colors"
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Join our mailing list
            </p>
            <p className="text-slate-400 text-sm leading-relaxed mb-4">
              Subscribe to get new discounts delivered direct to you.
            </p>
            {status === 'success' ? (
              <p className="text-green-400 text-sm">You're in! We'll be in touch.</p>
            ) : (
              <form onSubmit={handleSubscribe} className="flex flex-col gap-2">
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setStatus('idle') }}
                  disabled={status === 'loading'}
                  required
                  className="w-full border border-navy-700 bg-navy-800 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={status === 'loading'}
                  className="w-full bg-orange-600 hover:bg-orange-700 text-white font-semibold rounded-lg py-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-navy-900 disabled:opacity-50"
                >
                  {status === 'loading' ? 'Subscribing…' : 'Subscribe'}
                </button>
                {(status === 'error' || status === 'duplicate') && (
                  <p className="text-red-400 text-xs">
                    {status === 'duplicate' ? 'That email is already subscribed.' : 'Something went wrong. Please try again.'}
                  </p>
                )}
              </form>
            )}
          </div>
        </div>

        <div className="border-t border-navy-800 mt-8 pt-6 text-center">
          <p className="text-slate-500 text-xs">
            © {new Date().getFullYear()} BikeGrid. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}
