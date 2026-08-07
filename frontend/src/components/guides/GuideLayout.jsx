import { Link } from 'react-router-dom'
import { canonicalFor, buildBreadcrumbJsonLd } from '../../seo'
import { GUIDES } from '../../content/guides'

// Shared chrome for every guide page. Its real job is owning the metadata block
// — a guide that forgets its canonical is a guide Google may drop, and the
// prerender would silently fall back to a derived one rather than failing.
export default function GuideLayout({ title, description, path, heading, subline, children }) {
  const isHub = path === '/guides'
  const others = GUIDES.filter((g) => g.path !== path)
  // Short label for the crumb — the page heading is a sentence, not a crumb.
  const crumb = GUIDES.find((g) => g.path === path)?.label ?? heading

  const trail = [{ name: 'Deals', path: '/' }, { name: 'Guides', path: '/guides' }]
  if (!isHub) trail.push({ name: crumb, path })

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <title>{title}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={canonicalFor(path)} />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(buildBreadcrumbJsonLd(trail)) }}
      />

      <nav className="text-sm text-slate-500 mb-6 flex items-center gap-1.5 flex-wrap">
        <Link to="/" className="hover:text-orange-600">Deals</Link>
        <span>/</span>
        {isHub ? (
          <span className="text-slate-700">Guides</span>
        ) : (
          <>
            <Link to="/guides" className="hover:text-orange-600">Guides</Link>
            <span>/</span>
            <span className="text-slate-700">{crumb}</span>
          </>
        )}
      </nav>

      <h1 className="text-2xl font-semibold text-slate-900 mb-2">{heading}</h1>
      {subline && <p className="text-sm text-slate-400 mb-8">{subline}</p>}

      {children}

      {!isHub && (
        <section className="mt-14 pt-8 border-t border-slate-200">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
            More guides
          </h2>
          <ul className="space-y-2">
            {others.map((g) => (
              <li key={g.path}>
                <Link to={g.path} className="text-orange-600 hover:underline text-sm">
                  {g.label}
                </Link>
              </li>
            ))}
            <li>
              <Link to="/guides" className="text-orange-600 hover:underline text-sm">
                All guides
              </Link>
            </li>
          </ul>
        </section>
      )}
    </div>
  )
}
