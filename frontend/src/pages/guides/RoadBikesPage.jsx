import { Link } from 'react-router-dom'
import GuideLayout from '../../components/guides/GuideLayout'
import AtAGlanceCard from '../../components/guides/AtAGlanceCard'
import CatalogRail from '../../components/CatalogRail'
import { usePins } from '../../hooks/usePins'

export default function RoadBikesPage() {
  const { pinnedIds, togglePin } = usePins()

  return (
    <GuideLayout
      title="Road Bike Guide: Who They Suit and What to Spend · BikeGrid"
      description="Why road bikes are shaped the way they are, what drop bars and skinny tyres do for you, who they suit, and what you get at each price. With live deals."
      path="/guides/road-bikes"
      heading="The road bike guide"
      subline="The fastest way to cover ground under your own power"
    >
      <div className="guide-prose">
        <p>
          A road bike is optimised for sustained speed on sealed roads, and everything about it
          serves that. The frame is light and stiff so your effort goes into the wheels rather than
          into flexing the bike. The tyres are narrow and smooth because that rolls faster on
          tarmac. And the <strong>drop handlebars</strong>, the curled-under ones, let you get low,
          which matters because above about 20km/h most of your effort goes into pushing air out of
          the way.
        </p>
        <p>
          The drops also give you three or four hand positions, which is the more practical reason
          they exist. On a four-hour ride, being able to move your hands around is worth more than
          it sounds.
        </p>
      </div>

      <AtAGlanceCard
        items={[
          { label: 'Surface', value: 'Sealed road, which is the whole design brief.' },
          { label: 'Position', value: 'Low and stretched forward. Fast, and takes some getting used to.' },
          { label: 'Tyres', value: '25 to 32mm, smooth. Modern bikes trend wider than they used to.' },
          { label: 'Typical new price', value: '$1,200 entry alloy, $3,000 and up for carbon' },
        ]}
      />

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">Who it suits</h2>
        <div className="guide-prose">
          <p>
            Buy a road bike if you want to ride 30km or more at a time, on roads, and the ride
            itself is the point. Fitness, weekend group rides, a long sealed commute, eventually a
            gran fondo or a charity century. For that kind of riding nothing else comes close.
          </p>
          <p>
            It is a poor fit if your route includes gravel, potholes you cannot dodge, or a kerb
            you need to hop. It is also a poor fit if what you actually do is ride 5km to work. You
            will be uncomfortable, and a <Link to="/guides/commuter-bikes">commuter bike</Link>{' '}
            would serve you better every day.
          </p>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">
          Endurance or race geometry?
        </h2>
        <div className="guide-prose">
          <p>
            Road bikes come in two shapes and shops do not always explain the difference.{' '}
            <strong>Endurance</strong> geometry puts the handlebars a bit higher and the wheelbase
            a bit longer, so it is more comfortable and more stable, with clearance for wider
            tyres. This is what most people should buy, including many who think they want the
            other one.
          </p>
          <p>
            <strong>Race</strong> geometry is lower and twitchier. It is faster if you are racing
            and flexible enough to hold the position. If you are not doing both of those things, it
            mostly just hurts your back.
          </p>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">What the money buys</h2>
        <div className="guide-prose">
          <p>
            Below about $1,200 you are getting a heavy frame and gears that shift vaguely. Around
            $1,500 to $2,500 is the sweet spot: a good alloy or entry carbon frame, hydraulic disc
            brakes, and a groupset (the gears and brakes) like Shimano 105 or SRAM Rival that works
            properly and keeps working.
          </p>
          <p>
            Above $4,000 you are buying lighter carbon, electronic shifting and deeper wheels. All
            nice, none of it necessary. Most riders on a $2,000 bike are not being held back by the
            bike.
          </p>
          <p>
            The upgrade worth prioritising at any price is <strong>wheels</strong>, and after that
            a bike fit. Both do more for how the bike feels than a frame upgrade will.
          </p>
        </div>
      </section>

      <CatalogRail
        title="Road bikes on sale right now"
        params={{ category: ['Road'] }}
        ctaLabel="Browse all road bike deals"
        ctaTo="/road-bikes"
        pinnedIds={pinnedIds}
        onTogglePin={togglePin}
      />

      <div className="guide-prose mt-8">
        <p>
          Want similar speed with room for dirt roads? Read the{' '}
          <Link to="/guides/gravel-bikes">gravel bike guide</Link>. It is much the same bike with
          more tyre clearance.
        </p>
      </div>
    </GuideLayout>
  )
}
