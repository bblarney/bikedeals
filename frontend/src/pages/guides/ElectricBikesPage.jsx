import { Link } from 'react-router-dom'
import GuideLayout from '../../components/guides/GuideLayout'
import ComparisonTable from '../../components/guides/ComparisonTable'
import AtAGlanceCard from '../../components/guides/AtAGlanceCard'
import CatalogRail from '../../components/CatalogRail'
import { usePins } from '../../hooks/usePins'

const SECTIONS = [
  { id: 'city-commuter', label: 'City & commuter e-bikes' },
  { id: 'cargo', label: 'Cargo e-bikes' },
  { id: 'e-mtb', label: 'Electric mountain bikes' },
  { id: 'e-road', label: 'Electric road & fast hybrids' },
]

const SUBTYPES = {
  columns: ['Sub-type', 'Built for', 'Rough price', 'Watch out for'],
  rows: [
    [
      'City / commuter',
      'Getting to work, shops, school run',
      '$1,500 to $4,000',
      'Weight. Check you can lift it up a step',
    ],
    [
      'Cargo',
      'Kids, groceries, replacing car trips',
      '$4,000 to $10,000',
      'Where you will park it. They are long',
    ],
    [
      'Electric mountain',
      'Trails, big climbs, more laps',
      '$4,000 to $15,000',
      'Full-suspension e-MTBs need real servicing',
    ],
    [
      'Electric road / fast hybrid',
      'Longer road rides, hilly commutes',
      '$3,000 to $12,000',
      'Smaller batteries, so check the range claim',
    ],
  ],
}

const FAQ = [
  {
    q: 'Do I need a licence or registration?',
    a: 'No, not for a bike that meets the 250W and 25km/h pedal-assist rules, which covers essentially everything sold by a normal bike shop. It counts as a bicycle. Bikes with higher-power motors, or a throttle that works without pedalling, are a different matter and are not road-legal in most Australian states.',
  },
  {
    q: 'How long does the battery last?',
    a: 'Per charge, 40 to 100km depending on the battery, the hills, your weight and which assistance mode you use. Over its life, expect 500 to 1,000 full charge cycles, or around 3 to 5 years of regular riding, before capacity drops noticeably. A replacement battery is a real cost, so ask what one is worth for the model you are buying.',
  },
  {
    q: 'Can I ride it in the rain?',
    a: 'Yes. Motors and batteries on reputable bikes are sealed for weather. Avoid pressure-washing it and avoid leaving it submerged, and it will be fine.',
  },
  {
    q: 'Is it still exercise?',
    a: 'Yes, and this surprises people. Studies consistently find e-bike riders get moderate-intensity exercise, because the motor lowers the effort per trip but people take more trips and ride further.',
  },
  {
    q: 'Can my local shop service it?',
    a: 'Worth asking before you buy. Motor systems from the big names (Bosch, Shimano, Brose, Bafang, Specialized, Giant) are widely supported. A no-name direct-import motor can leave you with a bike no one in town will touch, which is the most common way an e-bike bargain turns expensive.',
  },
]

export default function ElectricBikesPage() {
  // One pin store for the whole page. See the note in CatalogRail about why
  // each rail must not call usePins() for itself.
  const { pinnedIds, togglePin } = usePins()
  const pins = { pinnedIds, onTogglePin: togglePin }

  return (
    <GuideLayout
      title="Electric Bike Guide: Types, Costs and Who They Suit · BikeGrid"
      description="What an e-bike is, how cargo, e-MTB, electric road and city e-bikes differ, what they cost in Australia and how to pick one. With live deals from local shops."
      path="/guides/electric-bikes"
      heading="The electric bike guide"
      subline="The newest category, and the one with the most confusing marketing"
    >
      <div className="guide-prose">
        <p>
          An e-bike is a normal bike with a motor that helps while you pedal. That last part
          matters. On almost every e-bike sold in an Australian bike shop, the motor only does
          anything <strong>while you are pedalling</strong>, so you still ride it like a bike. You
          just arrive a lot fresher.
        </p>
        <p>
          The useful way to think about it is that an e-bike is one of the other bike types with
          assistance added. There are electric mountain bikes, electric commuters, electric cargo
          bikes and electric road bikes, and they differ from each other as much as their
          non-electric versions do. The word "e-bike" describes the motor, not the bike.
        </p>
      </div>

      <AtAGlanceCard
        items={[
          {
            label: 'What the motor does',
            value: 'Multiplies your effort, usually 2 to 4 times. You still pedal, but hills stop mattering much.',
          },
          {
            label: 'Legal limits in Australia',
            value: '250W continuous, with assistance cutting out at 25 km/h. Above that it is legally a motorbike.',
          },
          {
            label: 'Realistic range',
            value: '40 to 100km depending on battery size, hills, your weight and how much you lean on it. Assume the low end.',
          },
          {
            label: 'The catch',
            value: 'Weight of 20 to 30kg, and servicing. Budget for a proper shop rather than a mate with allen keys.',
          },
        ]}
      />

      <nav className="bg-white border border-slate-200 rounded-xl p-5 my-8">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          The four kinds
        </p>
        <ul className="grid gap-2 sm:grid-cols-2">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`} className="text-sm text-orange-600 hover:underline">
                {s.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <ComparisonTable columns={SUBTYPES.columns} rows={SUBTYPES.rows} />

      <CatalogRail
        title="Electric bikes on sale right now"
        params={{ category: ['E-Bike'] }}
        ctaLabel="Browse all e-bike deals"
        ctaTo="/?category=E-Bike"
        {...pins}
      />

      {/* ---------- City / commuter ---------- */}
      <section id="city-commuter" className="mt-14 scroll-mt-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-3">City &amp; commuter e-bikes</h2>
        <div className="guide-prose">
          <p>
            The most common kind of e-bike by a wide margin. Flat bars, upright position, usually
            mudguards and a rack, and often a step-through frame so you don't have to swing a leg
            over anything. Built to be ridden in work clothes.
          </p>
          <p>
            This is the bike that turns a 12km commute you would never do into one you do four
            times a week. The appeal is that you arrive without needing a shower, and that hills
            and headwinds stop being a reason to drive.
          </p>
          <p>
            <strong>What to look for:</strong> a rack and mudguards fitted from the factory, a
            battery you can remove to charge inside, and lights wired into the main battery.
            Hub-drive motors, which sit in the rear wheel, are cheaper and fine for flat cities.{' '}
            <strong>Mid-drive</strong> motors, at the pedals, cost more and are noticeably better
            if you live somewhere hilly.
          </p>
          <p>
            <strong>Watch out for:</strong> weight. A 25kg bike is fine to ride and awful to carry
            up a flight of stairs. If your bike will live in an apartment, check this in person
            before anything else.
          </p>
        </div>
        <CatalogRail
          title="Commuter e-bike deals"
          params={{ category: ['E-Bike'], q: 'commuter' }}
          ctaLabel="See commuter e-bikes"
          ctaTo="/?category=E-Bike&q=commuter"
          {...pins}
        />
      </section>

      {/* ---------- Cargo ---------- */}
      <section id="cargo" className="mt-14 scroll-mt-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-3">Cargo e-bikes</h2>
        <div className="guide-prose">
          <p>
            A stretched, reinforced frame built to carry serious weight, typically two kids or a
            full grocery shop. Without a motor these are hard work. With one they can replace a
            second car for most trips, which is a large part of why they cost what they cost.
          </p>
          <p>
            Two shapes dominate. <strong>Longtails</strong> stretch the back of the bike and put
            the load behind you, so they ride much like a normal bike and fit through normal gaps.{' '}
            <strong>Front-loaders</strong>, sometimes called bakfiets, put a box between you and
            the front wheel so you can see the cargo. Better for small children, though the
            steering takes about a week to get used to.
          </p>
          <p>
            <strong>What to look for:</strong> a mid-drive motor is close to mandatory, since you
            are asking it to move 100kg or more from a standstill. Check the rated payload rather
            than just the seat count, and look for hydraulic disc brakes. Stopping a loaded cargo
            bike is a real job.
          </p>
          <p>
            <strong>Watch out for:</strong> parking. These run 2 to 2.7m long and rarely fit a
            normal bike rack, a lift, or a standard garden shed. Work out where it will live before
            you buy rather than after.
          </p>
        </div>
        <CatalogRail
          title="Cargo e-bike deals"
          params={{ category: ['E-Bike'], q: 'cargo' }}
          ctaLabel="See cargo e-bikes"
          ctaTo="/?category=E-Bike&q=cargo"
          note="Cargo bikes are a small slice of the catalog, so this is a thin list. Some shops also file them under commuter bikes."
          {...pins}
        />
      </section>

      {/* ---------- e-MTB ---------- */}
      <section id="e-mtb" className="mt-14 scroll-mt-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-3">Electric mountain bikes</h2>
        <div className="guide-prose">
          <p>
            A full mountain bike, with suspension, grippy tyres and proper brakes, plus a mid-drive
            motor. What you get out of it is climbing. Gravity already handles the descent, but the
            motor means you can get back to the top three times in the time it used to take you
            once.
          </p>
          <p>
            They come in the same flavours as regular mountain bikes.{' '}
            <strong>Hardtail e-MTBs</strong>, with suspension at the front only, are cheaper,
            lighter and simpler, and plenty for fire roads and smoother singletrack.{' '}
            <strong>Full-suspension e-MTBs</strong> add a rear shock, which is what you want for
            rough, steep, technical trails.
          </p>
          <p>
            <strong>What to look for:</strong> battery size in watt-hours, because climbing drains
            a battery much faster than commuting does. Look for 600Wh or more if you are doing long
            days. It is also worth checking trail access, since some parks and reserves restrict
            e-MTBs.
          </p>
          <p>
            <strong>Watch out for:</strong> running costs. A full-suspension e-MTB is a
            high-maintenance machine, with suspension servicing, drivetrain wear accelerated by the
            motor's torque, and eventually a battery replacement.
          </p>
        </div>
        <CatalogRail
          title="Electric mountain bike deals"
          params={{ category: ['E-Bike'], q: 'electric mountain' }}
          ctaLabel="See electric mountain bikes"
          ctaTo="/?category=E-Bike&q=electric+mountain"
          {...pins}
        />
      </section>

      {/* ---------- e-road ---------- */}
      <section id="e-road" className="mt-14 scroll-mt-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-3">
          Electric road bikes &amp; fast hybrids
        </h2>
        <div className="guide-prose">
          <p>
            The smallest and least understood category. These are road or fast-hybrid bikes with a
            deliberately small, light motor and battery, aiming for a bike that still feels and
            weighs like a road bike but with enough assistance to flatten the hills.
          </p>
          <p>
            Two groups tend to buy them: riders who want to keep up with a faster group, and riders
            who have had an injury or an illness, or simply a few more birthdays, and want their
            old rides back.
          </p>
          <p>
            <strong>What to look for:</strong> total weight, which is really the whole point. A
            good one is 12 to 15kg rather than 25kg. Expect a smaller battery of 250 to 450Wh, and
            a motor tuned to add a modest amount rather than shove you along.
          </p>
          <p>
            <strong>Watch out for:</strong> range claims made at the lowest assistance setting. If
            you ride in the top mode on a hilly route, expect roughly half the advertised number.
          </p>
        </div>
        <CatalogRail
          title="Electric road and fast hybrid deals"
          params={{ category: ['E-Bike'], q: 'road' }}
          ctaLabel="See electric road bikes"
          ctaTo="/?category=E-Bike&q=road"
          note={'Shops rarely label these "e-road", so this search also picks up allroad and fast-hybrid models from the same family.'}
          {...pins}
        />
      </section>

      {/* ---------- FAQ ---------- */}
      <section className="mt-14">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Common questions</h2>
        <div className="space-y-5">
          {FAQ.map(({ q, a }) => (
            <div key={q}>
              <h3 className="text-sm font-semibold text-slate-800 mb-1.5">{q}</h3>
              <p className="text-sm text-slate-600 leading-relaxed">{a}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-12">
        <div className="guide-prose">
          <p>
            Still deciding between electric and not? The{' '}
            <Link to="/guides">bike type guides</Link> cover what each non-electric category is
            for, and every one of them has an electric version.
          </p>
        </div>
      </section>
    </GuideLayout>
  )
}
