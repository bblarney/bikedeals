import { canonicalFor } from '../seo'

export default function ContactPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <title>Contact — BikeGrid</title>
      <meta name="description" content="Get in touch with the BikeGrid team. Questions, shop listing requests, or problem reports — we're here to help." />
      <link rel="canonical" href={canonicalFor('/contact')} />
      <h1 className="text-2xl font-semibold text-slate-900 mb-2">Contact</h1>
      <p className="text-sm text-slate-400 mb-8">We&apos;ll get back to you as soon as we can.</p>

      <div className="bg-white border border-slate-200 rounded-xl p-8 space-y-6">
        <div>
          <h2 className="text-base font-semibold text-slate-800 mb-1">General enquiries</h2>
          <p className="text-slate-600 text-sm mb-3">
            Questions about the site, missing deals, or anything else.
          </p>
          <a href="mailto:info@bikegrid.com.au" className="text-blue-600 hover:underline text-sm">info@bikegrid.com.au</a>
        </div>

        <div className="border-t border-slate-100 pt-6">
          <h2 className="text-base font-semibold text-slate-800 mb-1">Shop listings</h2>
          <p className="text-slate-600 text-sm">
            Own a bike shop and want to be listed? Email us with your shop name, location, and
            website and we&apos;ll be in touch.
          </p>
        </div>

        <div className="border-t border-slate-100 pt-6">
          <h2 className="text-base font-semibold text-slate-800 mb-1">Report a problem</h2>
          <p className="text-slate-600 text-sm">
            Incorrect price, stale listing, or a broken link? Let us know and we&apos;ll fix it
            promptly.
          </p>
        </div>

        <div className="border-t border-slate-100 pt-6">
          <h2 className="text-base font-semibold text-slate-800 mb-1">Takedown requests</h2>
          <p className="text-slate-600 text-sm mb-2">
            If you are a retailer or rights holder and want your listings removed from BikeGrid,
            please contact us with your shop name, the relevant listing URLs, and the reason for
            your request. We will review and action all valid requests promptly.
          </p>
          <a href="mailto:info@bikegrid.com.au" className="text-blue-600 hover:underline text-sm">info@bikegrid.com.au</a>
        </div>
      </div>
    </div>
  )
}
