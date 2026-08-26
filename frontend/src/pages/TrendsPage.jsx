import { canonicalFor } from '../seo'
import { useMarket } from '../hooks/useMarket'
import {
  GROUPSET_BRAND_COLORS,
  MATERIAL_COLORS,
  SHIFTING_COLORS,
  inOrder,
  pick,
  pivot,
  toShares,
} from '../lib/market'
import ChartCard from '../components/trends/ChartCard'
import ShareChart from '../components/trends/ShareChart'
import PriceDistribution from '../components/trends/PriceDistribution'
import TopBrands from '../components/trends/TopBrands'
import GroupsetLadder from '../components/trends/GroupsetLadder'
import DiscountHeatmap from '../components/trends/DiscountHeatmap'
import DiscountDepth from '../components/trends/DiscountDepth'

const MATERIAL_ORDER = ['Carbon', 'Aluminium', 'Steel', 'Titanium']
const BRAND_ORDER = ['Shimano', 'SRAM', 'Campagnolo']
const SHIFTING_ORDER = ['Electronic', 'Mechanical']

function legendFor(series, colors) {
  return series.map((label) => ({ label, color: colors[label] }))
}

/**
 * Everything the charts need, derived once.
 *
 * Returns null before the single request lands, which is also the state the
 * build-time prerender renders in: React Query never fetches during
 * renderToString. So every heading, blurb, chart title and the methodology note
 * at the bottom is written outside this branch and reaches the static HTML;
 * only the plotted marks wait for data.
 */
function derive(data) {
  if (!data) return null
  const { points, coverage, total_listings: total } = data

  const materials = toShares(pivot(pick(points, 'material_by_band')))
  const groupsets = toShares(pivot(pick(points, 'groupset_brand_by_category')))
  const shifting = toShares(pivot(pick(points, 'shifting_by_band')))

  const brandTotals = {}
  for (const p of pick(points, 'groupset_brand_by_category')) {
    brandTotals[p.series] = (brandTotals[p.series] ?? 0) + p.n
  }

  return {
    points,
    total,
    materials: { ...materials, series: inOrder(materials.series, MATERIAL_ORDER) },
    groupsets: { ...groupsets, series: inOrder(groupsets.series, BRAND_ORDER) },
    shifting: { ...shifting, series: inOrder(shifting.series, SHIFTING_ORDER) },
    brandTotals,
    materialKnown: coverage.frame_material,
    groupsetKnown: coverage.drivetrain_groupset,
    onSale: pick(points, 'discount_hist').reduce((a, p) => a + p.n, 0),
  }
}

export default function TrendsPage() {
  const { data, isError } = useMarket()
  const m = derive(data)

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      <title>Australian Bike Market Trends: What Shops Are Stocking | BikeGrid</title>
      <meta
        name="description"
        content="What Australian bike shops are actually stocking right now: prices by category, Shimano versus SRAM, carbon versus alloy, and where the deepest discounts sit. Rebuilt daily from live shop inventories."
      />
      <link rel="canonical" href={canonicalFor('/trends')} />

      <h1 className="text-2xl font-semibold text-slate-900 mb-2">
        The Australian bike market, right now
      </h1>
      <p className="text-sm text-slate-400 mb-6">
        Rebuilt daily from live shop inventories
        {m ? ` · ${m.total.toLocaleString()} listings` : ''}
      </p>
      <p className="text-slate-600 leading-relaxed mb-10 max-w-3xl">
        Every night we read the catalogues of Australian bike shops. This page is what those
        catalogues add up to: what a bike of each type costs, which brands fill the floors, what
        spec your money buys, and where the discounts genuinely are. It is a snapshot of today,
        not a history, and it changes as the shops do.
      </p>

      {isError && (
        <p className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 mb-10">
          The market data could not be loaded just now. Please try again shortly.
        </p>
      )}

      <Section
        title="What's on the floor"
        blurb="Australian shops stock a very different mix at each price. Every figure counts listings the way the feed does: one card per product, however many sizes it comes in."
      >
        <ChartCard
          title="What a bike costs, by type"
          subtitle="Median price and the full spread of listings. Click a tile to browse that category."
          note="Medians are interpolated from the price bands, so they are accurate to within a band."
        >
          {m ? <PriceDistribution points={m.points} /> : <Placeholder height="h-64" />}
        </ChartCard>

        <ChartCard
          title="The 25 biggest brands on Australian shop floors"
          subtitle="Ranked by how many listings carry them, with the average discount on the discounted ones."
        >
          {m ? <TopBrands points={m.points} /> : <Placeholder height="h-72" />}
        </ChartCard>
      </Section>

      <Section
        title="What your money buys"
        blurb="Frame material and drivetrain are the two specs that move most with price. Shops publish them inconsistently, so these charts measure only the listings where the shop said so."
      >
        <ChartCard
          title="Carbon, alloy, steel and titanium, by price"
          subtitle="Where carbon overtakes aluminium is the clearest line in the Australian market."
          legend={m ? legendFor(m.materials.series, MATERIAL_COLORS) : null}
          note={m ? coverageNote(m.materialKnown, m.total, 'a frame material') : null}
        >
          {m ? (
            <ShareChart rows={m.materials.rows} series={m.materials.series} colors={MATERIAL_COLORS} />
          ) : (
            <Placeholder height="h-64" />
          )}
        </ChartCard>

        <ChartCard
          title="Shimano versus SRAM, by category"
          subtitle={
            m
              ? brandHeadline(m.brandTotals, m.groupsetKnown)
              : 'Groupset brand share across every category we track.'
          }
          legend={m ? legendFor(m.groupsets.series, GROUPSET_BRAND_COLORS) : null}
          note={m ? coverageNote(m.groupsetKnown, m.total, 'a groupset') : null}
        >
          {m ? (
            <ShareChart rows={m.groupsets.rows} series={m.groupsets.series} colors={GROUPSET_BRAND_COLORS} />
          ) : (
            <Placeholder height="h-64" />
          )}
        </ChartCard>

        <ChartCard
          title="Where electronic shifting starts"
          subtitle="Di2, AXS and eTap listings as a share of each price band."
          legend={m ? legendFor(m.shifting.series, SHIFTING_COLORS) : null}
          note={m ? coverageNote(m.groupsetKnown, m.total, 'a groupset') : null}
        >
          {m ? (
            <ShareChart rows={m.shifting.rows} series={m.shifting.series} colors={SHIFTING_COLORS} />
          ) : (
            <Placeholder height="h-64" />
          )}
        </ChartCard>

        <ChartCard
          title="Every groupset, by how many bikes carry it"
          subtitle="Colour is the brand. The volume sits a long way below the halo models."
          legend={legendFor(BRAND_ORDER, GROUPSET_BRAND_COLORS)}
        >
          {m ? <GroupsetLadder points={m.points} /> : <Placeholder height="h-72" />}
        </ChartCard>
      </Section>

      <Section
        title="Where the deals are"
        blurb={
          m
            ? `${m.onSale.toLocaleString()} of ${m.total.toLocaleString()} listings are discounted right now, and they are not spread evenly.`
            : 'Discounts are not spread evenly across categories or price points.'
        }
      >
        <ChartCard
          title="Average discount, by category and price"
          subtitle="Darker is deeper. Each cell shows the average discount and how many of its listings are on sale; click one to browse it."
          note="Averages cover discounted listings only, so a full-price-heavy cell still shows the depth you would get if you found one."
        >
          {m ? <DiscountHeatmap points={m.points} /> : <Placeholder height="h-64" />}
        </ChartCard>

        <ChartCard
          title="How deep the discounts run"
          subtitle="Every discounted listing on the site, by how far it is marked down."
        >
          {m ? <DiscountDepth points={m.points} /> : <Placeholder height="h-56" />}
        </ChartCard>
      </Section>

      <section className="mt-12 border-t border-slate-200 pt-6">
        <h2 className="text-base font-semibold text-slate-800 mb-3">How this page is built</h2>
        <div className="text-sm text-slate-600 leading-relaxed space-y-3 max-w-3xl">
          <p>
            Every figure here counts listings, not shops and not sizes: a bike published in five
            sizes across three of a chain's stores is one listing, the same way it is one card in
            the feed. Only in-stock listings are counted, and the whole page is rebuilt every
            night.
          </p>
          <p>
            Frame material and drivetrain are read out of the shop's own product description, and
            not every shop writes them down. Those two charts therefore describe the listings where
            the shop said so, which is a smaller and not perfectly representative slice of the
            market. Everything else covers the full catalogue.
          </p>
          <p>
            Prices are as listed by the retailer, and discounts are measured against the retailer's
            own stated RRP.
          </p>
        </div>
      </section>
    </div>
  )
}

function Section({ title, blurb, children }) {
  return (
    <section className="mb-12">
      <h2 className="text-lg font-semibold text-slate-900 mb-1">{title}</h2>
      <p className="text-sm text-slate-500 mb-6 max-w-3xl">{blurb}</p>
      {children}
    </section>
  )
}

/**
 * Stands in for a chart body before the data lands.
 *
 * A sized block rather than nothing, so the page does not reflow as seven
 * charts arrive at once, and so the prerendered HTML has the same shape as the
 * hydrated one.
 */
function Placeholder({ height }) {
  return <div className={`${height} rounded-lg bg-slate-50`} aria-hidden="true" />
}

function coverageNote(known, total, what) {
  if (!total) return null
  const pct = Math.round((known / total) * 100)
  return `Based on the ${known.toLocaleString()} listings (${pct}% of ${total.toLocaleString()}) where the shop published ${what}.`
}

function brandHeadline(totals, known) {
  if (!known) return 'Groupset brand share across every category we track.'
  const share = (name) => Math.round(((totals[name] ?? 0) / known) * 100)
  return `${share('Shimano')}% Shimano, ${share('SRAM')}% SRAM across every listing that names a groupset.`
}
