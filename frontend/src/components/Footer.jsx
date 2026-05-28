import { Link } from 'react-router-dom'

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
  return (
    <footer className="bg-slate-900 mt-auto">
      <div className="max-w-7xl mx-auto px-6 py-10">
        <div className="grid gap-8 sm:grid-cols-3">
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
        </div>

        <div className="border-t border-slate-800 mt-8 pt-6 text-center">
          <p className="text-slate-500 text-xs">
            © {new Date().getFullYear()} BikeGrid. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}
