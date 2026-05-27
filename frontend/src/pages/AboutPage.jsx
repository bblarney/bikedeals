export default function AboutPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <title>About BikeDeals — How We Find the Best Bike Deals</title>
      <meta name="description" content="BikeDeals automatically scans local Australian bike shop inventories every day to surface the best discounts in one place." />
      <link rel="canonical" href="https://bikedeals.com.au/about" />
      <h1 className="text-2xl font-semibold text-slate-900 mb-2">About BikeDeals</h1>
      <p className="text-sm text-slate-400 mb-8">Updated daily · Australia-wide</p>

      <section className="mb-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">What we do</h2>
        <p className="text-slate-600 leading-relaxed mb-3">
          BikeDeals automatically scans local bike shop inventories every day and surfaces the best
          discounts in one place. Instead of checking a dozen shop sites, you get a single feed of
          in-stock deals sorted by discount — updated daily.
        </p>
        <p className="text-slate-600 leading-relaxed">
          Prices shown are as-listed by the retailer. Always confirm availability and final pricing
          directly with the shop before purchasing.
        </p>
      </section>

      <section>
        <h2 className="text-base font-semibold text-slate-800 mb-3">Contact</h2>
        <p className="text-slate-600 leading-relaxed">
          Contact form coming soon.
        </p>
      </section>
    </div>
  )
}
