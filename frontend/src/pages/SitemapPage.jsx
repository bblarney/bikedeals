import { Link } from 'react-router-dom'
import { canonicalFor } from '../seo'

const CATEGORIES = ['Road', 'Mountain', 'Gravel', 'E-Bike', 'Commuter']

export default function SitemapPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <title>Sitemap — BikeGrid</title>
      <meta name="description" content="All pages on BikeGrid, including category shortcuts for road, mountain, gravel, e-bike, and commuter bikes." />
      <link rel="canonical" href={canonicalFor('/sitemap')} />
      <h1 className="text-2xl font-semibold text-slate-900 mb-2">Sitemap</h1>
      <p className="text-sm text-slate-400 mb-8">All pages and category shortcuts.</p>

      <div className="grid gap-8 sm:grid-cols-2">
        <div>
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Browse by category
          </h2>
          <ul className="space-y-2">
            <li>
              <Link
                to="/"
                className="text-orange-600 hover:text-orange-700 text-sm font-medium"
              >
                All deals
              </Link>
            </li>
            {CATEGORIES.map((cat) => (
              <li key={cat}>
                <Link
                  to={`/?category=${encodeURIComponent(cat)}`}
                  className="text-orange-600 hover:text-orange-700 text-sm"
                >
                  {cat} bikes
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Company
          </h2>
          <ul className="space-y-2">
            {[
              { to: '/about', label: 'About BikeGrid' },
              { to: '/contact', label: 'Contact' },
              { to: '/terms', label: 'Terms of Use' },
              { to: '/privacy', label: 'Privacy Policy' },
              { to: '/sitemap', label: 'Sitemap' },
            ].map(({ to, label }) => (
              <li key={to}>
                <Link to={to} className="text-orange-600 hover:text-orange-700 text-sm">
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
