import { Link } from 'react-router-dom'
import { feedHref, fmtPct, pick } from '../../lib/market'

const BAR_COLOR = '#2a78d6'      // categorical slot 1
const DISCOUNT_COLOR = '#ea580c' // orange-600, the site accent

/**
 * Who fills Australian shop floors, and who is discounting.
 *
 * Two measures on one row, but never on two y-scales: the bar is the count and
 * the discount rides as its own small labelled figure beside it. Hand-built
 * rather than a recharts BarChart because each row is a link into the feed and
 * the labels must stay readable at 25 rows.
 */
export default function TopBrands({ points }) {
  const brands = pick(points, 'brands')
  if (!brands.length) return null
  const max = Math.max(...brands.map((b) => b.n))

  return (
    <ol className="space-y-1">
      {brands.map((brand) => (
        <li key={brand.series}>
          <Link
            to={feedHref({ brand: brand.series })}
            className="group grid grid-cols-[8rem_1fr_auto] sm:grid-cols-[10rem_1fr_auto] items-center gap-3 rounded-lg px-2 py-1 hover:bg-slate-50 transition"
          >
            <span className="text-xs text-slate-600 truncate group-hover:text-orange-600">
              {brand.series}
            </span>
            <span className="flex items-center gap-2">
              <span
                className="h-3 rounded-[3px]"
                style={{
                  width: `${Math.max((brand.n / max) * 100, 1)}%`,
                  backgroundColor: BAR_COLOR,
                }}
              />
              <span className="text-xs text-slate-500 tabular-nums">
                {brand.n.toLocaleString()}
              </span>
            </span>
            <span
              className="text-xs tabular-nums w-20 text-right"
              style={{ color: brand.value ? DISCOUNT_COLOR : CHART_MUTED }}
              title="Average discount among this brand's discounted listings"
            >
              {brand.value ? `${fmtPct(brand.value)} off` : 'full price'}
            </span>
          </Link>
        </li>
      ))}
    </ol>
  )
}

const CHART_MUTED = '#94a3b8' // slate-400
