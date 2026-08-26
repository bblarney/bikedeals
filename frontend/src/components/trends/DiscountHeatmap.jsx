import { Link } from 'react-router-dom'
import {
  CATEGORY_ORDER,
  DISCOUNT_RAMP,
  feedHref,
  inOrder,
  pick,
} from '../../lib/market'

/**
 * Where the discounts actually are: category against price band, shaded by how
 * deep the average discount runs.
 *
 * A hand-built grid rather than a charting library, for three reasons: every
 * cell is a link into the feed with those exact filters, every cell carries its
 * own visible number (the ramp's lighter steps fall below 3:1 on white, so
 * colour is never the only channel), and the second measure a cell needs -- how
 * many listings back the average -- rides in the same tile instead of demanding
 * a second scale.
 */
// Below this many discounted listings, a cell's average is noise.
const MIN_CELL_SAMPLE = 10

export default function DiscountHeatmap({ points }) {
  const depth = pick(points, 'discount_depth')
  const totals = pick(points, 'cell_totals')
  if (!depth.length) return null

  const bands = [...new Set(totals.map((p) => p.bucket))]
  const categories = inOrder([...new Set(totals.map((p) => p.series))], CATEGORY_ORDER)

  const key = (band, category) => `${band}|${category}`
  const depthBy = new Map(depth.map((p) => [key(p.bucket, p.series), p]))
  const totalBy = new Map(totals.map((p) => [key(p.bucket, p.series), p.n]))
  // Shade the ramp against well-supported cells only. Without this a cell like
  // sub-$1k e-bikes, where three discounted listings average 42%, sets the top
  // of the scale and paints itself the darkest square on the grid: the eye
  // reads "the best deals in Australia" off a sample of three.
  const trusted = depth.filter((p) => p.n >= MIN_CELL_SAMPLE)
  const maxDepth = Math.max(...(trusted.length ? trusted : depth).map((p) => p.value ?? 0), 1)

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] border-separate border-spacing-1 text-xs">
        <caption className="sr-only">
          Average discount by bike category and price band
        </caption>
        <thead>
          <tr>
            <th scope="col" className="text-left font-medium text-slate-500 pr-2" />
            {categories.map((category) => (
              <th key={category} scope="col" className="font-medium text-slate-500 pb-1">
                {category}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bands.map((band) => (
            <tr key={band}>
              <th scope="row" className="text-left font-medium text-slate-500 pr-2 whitespace-nowrap">
                {band}
              </th>
              {categories.map((category) => (
                <Cell
                  key={category}
                  band={band}
                  category={category}
                  point={depthBy.get(key(band, category))}
                  total={totalBy.get(key(band, category)) ?? 0}
                  maxDepth={maxDepth}
                />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Cell({ band, category, point, total, maxDepth }) {
  if (!total) {
    return (
      <td className="rounded-md bg-slate-50 text-center py-2 text-slate-300" aria-label="no listings">
        &ndash;
      </td>
    )
  }
  const avg = point?.value ?? 0
  const onSale = point?.n ?? 0
  // Too few discounted listings to shade: the number stays visible and
  // clickable, but it is not allowed to carry colour it has not earned.
  const thin = onSale > 0 && onSale < MIN_CELL_SAMPLE
  const step = avg && !thin
    ? DISCOUNT_RAMP[Math.min(
        Math.floor((avg / maxDepth) * DISCOUNT_RAMP.length),
        DISCOUNT_RAMP.length - 1,
      )]
    : '#f1f5f9'
  // The ramp runs light to dark, so ink has to flip once the fill gets dark
  // enough to swallow slate-900.
  const dark = DISCOUNT_RAMP.indexOf(step) >= 3

  return (
    <td className="p-0">
      <Link
        to={feedHref({ category, band })}
        className="block rounded-md py-2 text-center transition hover:ring-2 hover:ring-orange-400"
        style={{ backgroundColor: step, color: dark ? '#ffffff' : '#0f172a' }}
        title={
          thin
            ? `${category}, ${band}: only ${onSale} of ${total} listings on sale, too few to shade`
            : `${category}, ${band}: ${onSale} of ${total} listings on sale`
        }
      >
        <span className={`block font-semibold tabular-nums ${thin ? 'text-slate-400' : ''}`}>
          {avg ? `${Math.round(avg)}%` : '–'}
        </span>
        <span className={`block text-[10px] tabular-nums ${dark ? 'text-white/70' : 'text-slate-500'}`}>
          {onSale}/{total}
        </span>
      </Link>
    </td>
  )
}
