import { Link } from 'react-router-dom'
import GuideLayout from '../../components/guides/GuideLayout'
import AtAGlanceCard from '../../components/guides/AtAGlanceCard'
import ComparisonTable from '../../components/guides/ComparisonTable'
import CatalogRail from '../../components/CatalogRail'
import { usePins } from '../../hooks/usePins'

const VS = {
  columns: ['', 'Road', 'Gravel', 'Mountain'],
  rows: [
    ['Handlebars', 'Drop', 'Drop, often flared', 'Flat'],
    ['Tyre width', '25 to 32mm', '38 to 50mm', '55 to 65mm'],
    ['Suspension', 'None', 'None, usually', '100 to 170mm'],
    ['Fastest on tarmac', 'Yes', 'Nearly', 'No'],
    ['Handles rough trail', 'No', 'Up to a point', 'Yes'],
  ],
}

export default function GravelBikesPage() {
  const { pinnedIds, togglePin } = usePins()

  return (
    <GuideLayout
      title="Gravel Bike Guide: The Do-Everything Bike · BikeGrid"
      description="What a gravel bike is, how it differs from a road bike and a mountain bike, and why it suits riders who want one bike for mixed surfaces. With live deals."
      path="/guides/gravel-bikes"
      heading="The gravel bike guide"
      subline="If you can only own one bike, it is probably this one"
    >
      <div className="guide-prose">
        <p>
          A gravel bike is a road bike that has stopped being precious about the surface. Same drop
          handlebars, same general shape, same efficiency, but with room for tyres nearly twice as
          wide, a slightly taller and more relaxed frame, and lower gears for grinding up loose
          climbs.
        </p>
        <p>
          It is the newest of the main categories, and it exists because of how people actually
          ride. Most rides are not purely road or purely trail. They are a bit of road to get out
          of town, then a dirt road, then a bike path, then road home. A road bike is nervous on
          two of those and a mountain bike is slow on two of them, while a gravel bike is decent at
          all four.
        </p>
      </div>

      <AtAGlanceCard
        items={[
          { label: 'Surface', value: 'Tarmac, dirt roads, rail trails, easy singletrack.' },
          { label: 'Position', value: 'Leaned forward like a road bike, but a bit taller and calmer.' },
          { label: 'Tyres', value: '38 to 50mm with light tread, which is where most of the difference comes from.' },
          { label: 'Typical new price', value: '$1,500 entry alloy, $3,500 and up for carbon' },
        ]}
      />

      <ComparisonTable
        columns={VS.columns}
        rows={VS.rows}
        caption="Gravel sits deliberately in the middle, which is both the appeal and the compromise."
      />

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">Why it is often the sensible answer</h2>
        <div className="guide-prose">
          <p>
            Fit slick tyres and a gravel bike is maybe 5% slower than a{' '}
            <Link to="/guides/road-bikes">road bike</Link> on tarmac, a difference only a racer
            notices. Fit knobbly ones and it will handle most of what a{' '}
            <Link to="/guides/mountain-bikes">hardtail mountain bike</Link> handles, short of
            properly technical descents. Almost all of them have mounts for racks, mudguards and
            bags, so the same bike commutes, tours and does the Saturday ride.
          </p>
          <p>
            That is the case for it. Not that it is the best at any one thing, but that it is
            decent at all of them, and most people only have room and budget for one bike.
          </p>
          <p>
            The counterargument is worth taking seriously though. If you know that 95% of your
            riding is smooth tarmac, buy a road bike, and if you know it is technical trail, buy a
            mountain bike. A gravel bike is the right answer to uncertainty rather than to a clear
            brief.
          </p>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">What you would ride it for</h2>
        <div className="guide-prose">
          <ul>
            <li>Rail trails and dirt fire roads, which is the classic use</li>
            <li>Mixed-surface loops that link road sections with unsealed ones</li>
            <li>Bikepacking and touring, with bags strapped to the frame and forks</li>
            <li>Commuting on a route with potholes, tram tracks or a gravel shortcut</li>
            <li>Gravel events and long unsealed rides</li>
          </ul>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-base font-semibold text-slate-800 mb-3">What to look for</h2>
        <div className="guide-prose">
          <p>
            <strong>Tyre clearance</strong> is the spec that matters most, since a frame that takes
            45mm or more gives you far more options later than one capped at 38mm.{' '}
            <strong>Gearing</strong> matters next, because loose climbs need lower gears than road
            riding does, so look for a 1x setup or a wide-range cassette. Then check the{' '}
            <strong>mounts</strong>. Rack, mudguard and third bottle-cage bosses cost nothing to
            include and are frustrating to lack.
          </p>
          <p>
            Flared drop bars, where the drops angle outward, are common and worth having. They add
            stability on loose descents without costing you anything on the road.
          </p>
        </div>
      </section>

      <CatalogRail
        title="Gravel bikes on sale right now"
        params={{ category: ['Gravel'] }}
        ctaLabel="Browse all gravel bike deals"
        ctaTo="/gravel-bikes"
        pinnedIds={pinnedIds}
        onTogglePin={togglePin}
      />
    </GuideLayout>
  )
}
