import { Link } from 'react-router-dom'
import GuideLayout from '../../components/guides/GuideLayout'
import AtAGlanceCard from '../../components/guides/AtAGlanceCard'
import CatalogRail from '../../components/CatalogRail'
import { usePins } from '../../hooks/usePins'

export default function MountainBikesPage() {
  const { pinnedIds, togglePin } = usePins()

  return (
    <GuideLayout
      title="Mountain Bike Guide: Hardtail vs Full Suspension · BikeGrid"
      description="What makes a mountain bike a mountain bike, the difference between hardtail and full suspension, which trails suit which bike, and what to spend. With live deals."
      path="/guides/mountain-bikes"
      heading="The mountain bike guide"
      subline="Built to be ridden down things"
    >
      <div className="guide-prose">
        <p>
          A mountain bike is built around the assumption that the ground is going to hit you, and
          every design choice follows from that. Suspension to absorb it, fat knobbly tyres to grip
          loose dirt, powerful disc brakes to stop on a steep descent, and flat handlebars held
          wide for the leverage to steer through it.
        </p>
        <p>
          You sit fairly upright with your weight back, which is slow on the road and about right
          when you are pointing downhill. That is the trade-off: a mountain bike is the most
          capable bike off-road and the least efficient one on tarmac.
        </p>
      </div>

      <AtAGlanceCard
        items={[
          { label: 'Surface', value: 'Dirt trails, rocks, roots, mud. Anything unsealed.' },
          { label: 'Position', value: 'Upright, arms wide, weight back, ready to react.' },
          { label: 'Tyres', value: '2.2 to 2.6 inches wide with deep knobs. Grip over speed.' },
          { label: 'Typical new price', value: '$900 entry hardtail, $3,000 and up for full suspension' },
        ]}
      />

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">
          Hardtail or full suspension?
        </h2>
        <div className="guide-prose">
          <p>
            This is the decision that matters most. A <strong>hardtail</strong> has suspension at
            the front only. It is lighter, cheaper, needs less servicing, and transfers your
            pedalling more directly, which makes it better at climbing and better value at every
            price under about $2,500. It is also a good bike to learn on, because it punishes bad
            line choice and teaches you to pick better ones.
          </p>
          <p>
            <strong>Full suspension</strong> adds a rear shock. It is faster and much less tiring
            on rough, steep, technical trails, because the back wheel keeps tracking the ground
            instead of bouncing off it. It is also heavier, more expensive, and has pivots and a
            shock that need regular servicing.
          </p>
          <p>
            As a rule of thumb, below $2,500 buy the hardtail. A good hardtail will beat a cheap
            full-suspension bike, because a bad rear shock is worse than no rear shock. Above that,
            buy full suspension if your local trails are genuinely rough.
          </p>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">How it differs from a road bike</h2>
        <div className="guide-prose">
          <p>
            Almost completely. A <Link to="/guides/road-bikes">road bike</Link> has drop bars, 28mm
            slick tyres, no suspension, and puts you low and stretched out to cut through the air.
            A mountain bike has flat bars, tyres three times as wide, 100 to 170mm of suspension
            travel, and sits you upright.
          </p>
          <p>
            On a smooth road the road bike is much faster for the same effort. On a rocky descent
            the road bike is unrideable. They solve different problems rather than competing. If
            your riding is a bit of both, the answer is usually a{' '}
            <Link to="/guides/gravel-bikes">gravel bike</Link>.
          </p>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">What you would ride it for</h2>
        <div className="guide-prose">
          <ul>
            <li>Marked singletrack at a trail park or state forest</li>
            <li>Fire roads and rail trails, where any mountain bike is overkill but comfortable</li>
            <li>Bike park and downhill runs, where you take a lift up and ride down</li>
            <li>Cross-country loops, which are long and mixed with more climbing than descending</li>
            <li>Bikepacking on rough terrain, with gear strapped to the frame</li>
          </ul>
          <p>
            It is a poor choice for a daily road commute. It will do it, but you will be working
            about 30% harder than you need to, and knobbly tyres wear out fast on tarmac. A{' '}
            <Link to="/guides/commuter-bikes">commuter bike</Link> is the right tool there.
          </p>
        </div>
      </section>

      <CatalogRail
        title="Mountain bikes on sale right now"
        params={{ category: ['Mountain'] }}
        ctaLabel="Browse all mountain bike deals"
        ctaTo="/?category=Mountain"
        pinnedIds={pinnedIds}
        onTogglePin={togglePin}
      />

      <div className="guide-prose mt-8">
        <p>
          Want to get back up the hill faster? Electric mountain bikes are covered in the{' '}
          <Link to="/guides/electric-bikes#e-mtb">electric bike guide</Link>.
        </p>
      </div>
    </GuideLayout>
  )
}
