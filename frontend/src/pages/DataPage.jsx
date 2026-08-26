import { canonicalFor } from '../seo'

export default function DataPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <title>Data Services | BikeGrid</title>
      <meta name="description" content="BikeGrid tracks bike inventory and pricing across Australian shops every day. The underlying dataset is available to partners for research and analysis." />
      <link rel="canonical" href={canonicalFor('/data')} />
      <h1 className="text-2xl font-semibold text-slate-900 mb-2">Data services</h1>
      <p className="text-sm text-slate-400 mb-8">Bike pricing and inventory data, tailored to your needs.</p>

      <section className="mb-10">
        <p className="text-slate-600 leading-relaxed">
          BikeGrid tracks new-bike inventory and pricing across Australian bike shops every day.
          The dataset behind the site is available to partners for research, analysis, and
          internal use.
        </p>
      </section>

      <section className="mb-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">What&apos;s available</h2>
        <ul className="list-disc pl-5 space-y-2 text-slate-600 leading-relaxed">
          <li>Shop and brand coverage across Australia</li>
          <li>
            Normalised product records covering brand, model, category, frame size, frame
            material, groupset, price, and availability
          </li>
          <li>Historical pricing and discount movement over time</li>
          <li>Refreshed daily</li>
        </ul>
      </section>

      <section className="mb-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">Who it&apos;s for</h2>
        <ul className="list-disc pl-5 space-y-2 text-slate-600 leading-relaxed">
          <li>Brands and distributors tracking street pricing</li>
          <li>Retailers benchmarking against the market</li>
          <li>Researchers, media, and analysts</li>
        </ul>
      </section>

      <section className="mb-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">How it works</h2>
        <p className="text-slate-600 leading-relaxed">
          Extracts are tailored to the request. Scope, delivery format, and cadence (a one-off
          extract, scheduled delivery, or an ongoing feed) are agreed case by case.
        </p>
      </section>

      <div className="bg-white border border-slate-200 rounded-xl p-8">
        <h2 className="text-base font-semibold text-slate-800 mb-1">Make an enquiry</h2>
        <p className="text-slate-600 text-sm mb-3">
          Tell us what you&apos;re after: the coverage and fields you need, the timeframe, and how
          you&apos;d like it delivered. We&apos;ll come back to you with what we can do.
        </p>
        <a href="mailto:info@bikegrid.com.au" className="text-orange-600 hover:underline text-sm">info@bikegrid.com.au</a>
      </div>
    </div>
  )
}
