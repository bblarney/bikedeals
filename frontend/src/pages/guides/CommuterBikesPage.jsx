import { Link } from 'react-router-dom'
import GuideLayout from '../../components/guides/GuideLayout'
import AtAGlanceCard from '../../components/guides/AtAGlanceCard'
import CatalogRail from '../../components/CatalogRail'
import { usePins } from '../../hooks/usePins'

export default function CommuterBikesPage() {
  const { pinnedIds, togglePin } = usePins()

  return (
    <GuideLayout
      title="Commuter Bike Guide: Getting Around Town · BikeGrid"
      description="Flat-bar hybrids, city bikes, folding bikes and kids bikes. What to look for in a bike you ride in normal clothes, and what actually matters. With live deals."
      path="/guides/commuter-bikes"
      heading="The commuter bike guide"
      subline="The bikes that replace short car trips"
    >
      <div className="guide-prose">
        <p>
          Commuter bikes, also sold as hybrids, city bikes or urban bikes, are built around a
          different goal from the other categories. Not speed or capability, but that you ride the
          thing without having to think about it. Flat handlebars, an upright position so you can
          see traffic and traffic can see you, tyres wide enough for a pothole, and somewhere to
          put your stuff.
        </p>
        <p>
          Sitting upright costs you speed, because you make a bigger wall for the air to push
          against. Over 5km that costs you about a minute, and buys you the ability to look over
          your shoulder, ride in work clothes, and put a foot down at the lights without
          dismounting. For most short trips that is a good trade.
        </p>
      </div>

      <AtAGlanceCard
        items={[
          { label: 'Surface', value: 'Roads, bike paths, the occasional gravel shortcut.' },
          { label: 'Position', value: 'Upright, head up, hands relaxed.' },
          { label: 'Tyres', value: '32 to 45mm, light tread. Puncture-resistant is worth paying for.' },
          { label: 'Typical new price', value: '$500 basic, $1,200 and up for one you keep' },
        ]}
      />

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">
          A note on how this category is sorted
        </h2>
        <div className="guide-prose">
          <p>
            Worth knowing before you browse: "Commuter" is the broadest bucket on BikeGrid. Shops
            file a lot of things here that are not strictly commuter bikes. Hybrids and city bikes,
            yes, but also <strong>folding bikes</strong>, <strong>cruisers</strong>,{' '}
            <strong>kids bikes</strong> and <strong>BMX</strong>. It works out as a category for
            everything that is not road, gravel or mountain.
          </p>
          <p>
            So expect a mixed feed, and use the size and brand filters to narrow it down. If you
            are shopping for a child, this is the category to look in.
          </p>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">The four things that matter</h2>
        <div className="guide-prose">
          <p>
            Commuter bikes are where spec sheets matter least and practicality matters most. In
            rough order:
          </p>
          <ul>
            <li>
              <strong>Mudguards.</strong> The biggest single difference between a bike you ride
              year-round and one you ride when it is sunny. Fitted from the factory is ideal, and
              failing that, check the frame has mounts.
            </li>
            <li>
              <strong>A rack.</strong> Carrying weight on the bike instead of on your back is a
              real comfort upgrade. Panniers beat a backpack on any warm day.
            </li>
            <li>
              <strong>Puncture-resistant tyres.</strong> A flat on the way to work is the quickest
              way to stop commuting by bike, and they are worth the small weight penalty.
            </li>
            <li>
              <strong>Low-maintenance gearing.</strong> Internal hub gears or a simple 1x setup
              will shift when they are dirty and neglected, which is the state most commuters end
              up in.
            </li>
          </ul>
          <p>
            Two more that are easy to forget: <strong>lights</strong>, ideally hub-powered so they
            are never flat, and a <strong>lock</strong> budget of around 10% of the bike's value.
          </p>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">How it differs from a road bike</h2>
        <div className="guide-prose">
          <p>
            A <Link to="/guides/road-bikes">road bike</Link> asks you to change clothes, lean
            forward and go somewhere far. A commuter asks nothing in particular of you. Flat bars
            instead of drops, wider tyres, more upright, and enough mounting points to carry
            things.
          </p>
          <p>
            The categories do overlap at the edges. A "fitness hybrid" is essentially a road bike
            with flat bars, and it is a good choice if your commute is long and fast but you do not
            want drops.
          </p>
        </div>
      </section>

      <CatalogRail
        title="Commuter bikes on sale right now"
        params={{ category: ['Commuter'] }}
        ctaLabel="Browse all commuter bike deals"
        ctaTo="/commuter-bikes"
        pinnedIds={pinnedIds}
        onTogglePin={togglePin}
      />

      <div className="guide-prose mt-8">
        <p>
          If hills, sweat or a long commute are what is stopping you, an{' '}
          <Link to="/guides/electric-bikes#city-commuter">electric commuter</Link> deals with
          exactly those problems. It is the most popular kind of e-bike for good reason.
        </p>
      </div>
    </GuideLayout>
  )
}
