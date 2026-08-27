import { Link } from 'react-router-dom'
import GuideLayout from '../../components/guides/GuideLayout'
import ComparisonTable from '../../components/guides/ComparisonTable'
import { GUIDES } from '../../content/guides'
import { categoryPath } from '../../content/categories'

const COMPARISON = {
  columns: ['Type', 'Where it goes', 'Riding position', 'Best for'],
  rows: [
    ['Road', 'Sealed roads only', 'Low, leaned forward', 'Distance, speed, fitness'],
    ['Gravel', 'Road, dirt roads, easy trail', 'Leaned forward, but less extreme', 'One bike that does most things'],
    ['Mountain', 'Trails, rocks, roots, descents', 'Upright, arms wide', 'Technical off-road riding'],
    ['Commuter', 'Roads, bike paths, footpaths', 'Upright, head up', 'Short trips in normal clothes'],
    ['Electric', 'Depends on the model', 'Depends on the model', 'Hills, cargo, longer trips'],
  ],
}

export default function GuidesHubPage() {
  return (
    <GuideLayout
      title="Bike Buying Guides: Which Type of Bike Do I Need? · BikeGrid"
      description="New to bikes? Plain-English guides to road, gravel, mountain, commuter and electric bikes. What each one is for, who it suits, and live deals from Australian shops."
      path="/guides"
      heading="Which bike do you actually need?"
      subline="Five guides for anyone buying their first proper bike"
    >
      <div className="guide-prose">
        <p>
          Most bikes are specialised by two things: the surface you ride on, and how upright you
          sit. Nearly every difference between bike types comes back to one of those. Once you
          know which surface you'll be on and how far you're going, the choice narrows quickly.
        </p>
        <p>
          The main thing is to match the bike to the riding you'll do most weeks, rather than the
          riding you'd like to imagine doing. Plenty of people buy a road bike for a commute that
          turns out to include a gravel path and a set of stairs.
        </p>
      </div>

      <ComparisonTable
        columns={COMPARISON.columns}
        rows={COMPARISON.rows}
        caption="Electric gets its own row because an e-bike can be any of the other four with a motor added."
      />

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-4">The five guides</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {GUIDES.map((g) => (
            <Link
              key={g.path}
              to={g.path}
              className="group bg-white border border-slate-200 rounded-xl p-5 hover:border-orange-400 hover:shadow-md transition-all duration-150"
            >
              <p className="text-sm font-semibold text-slate-900 group-hover:text-orange-600 transition-colors mb-1.5">
                {g.label}
              </p>
              <p className="text-sm text-slate-600 leading-relaxed">{g.cardBlurb}</p>
              <p className="text-sm text-orange-600 mt-3">Read the guide →</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">
          Already know what you want?
        </h2>
        <p className="text-sm text-slate-600 leading-relaxed mb-4">
          Skip straight to the deals, sorted by discount:
        </p>
        <ul className="flex flex-wrap gap-2">
          {GUIDES.map((g) => (
            <li key={g.category}>
              <Link
                to={categoryPath(g.category)}
                className="inline-block text-sm text-slate-700 bg-white border border-slate-200 rounded-lg px-3 py-1.5 hover:border-orange-400 hover:text-orange-600 transition-colors"
              >
                {g.label}
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-12">
        <h2 className="text-base font-semibold text-slate-800 mb-3">
          Three questions that usually settle it
        </h2>
        <div className="guide-prose">
          <p>
            <strong>What is under your wheels?</strong> If it is sealed road the whole way, a road
            bike is the fastest thing you can ride. If any part of the route is dirt, gravel or
            grass, you want wider tyres, so look at gravel or commuter bikes. If it involves rocks,
            roots and steep descents, that is mountain bike territory.
          </p>
          <p>
            <strong>How far, and how often?</strong> Under about 10km a few times a week, comfort
            and practicality matter more than speed. You want to ride in normal clothes and not
            think about it. Once rides get longer, the leaned-forward position starts to earn its
            keep.
          </p>
          <p>
            <strong>What is stopping you riding more?</strong> If the honest answer is hills, a
            headwind, arriving sweaty, or hauling kids and shopping, then it is worth reading the{' '}
            <Link to="/guides/electric-bikes">electric bike guide</Link> before you settle on a
            type. A motor deals with those problems better than a lighter frame will.
          </p>
        </div>
      </section>

      <section className="mt-12">
        <h2 className="text-base font-semibold text-slate-800 mb-3">What to spend</h2>
        <div className="guide-prose">
          <p>
            Roughly, for a new bike from an Australian shop: under $700 is department-store
            territory, and tends to be heavy with parts that wear out quickly. $700 to $1,500 gets
            you a decent commuter or an entry-level hardtail. $1,500 to $3,000 is where road,
            gravel and trail bikes get properly good. Above that you are mostly buying lighter
            materials and smoother gear, with diminishing returns unless you are racing.
          </p>
          <p>
            E-bikes sit around $1,000 higher across the board, because the motor and battery are a
            real chunk of the cost.
          </p>
          <p>
            Those are list prices. Everything on BikeGrid is discounted stock from local shops, so
            the practical entry point for each band is lower.{' '}
            <Link to="/">Browse the current deals</Link> and sort by discount.
          </p>
        </div>
      </section>
    </GuideLayout>
  )
}
