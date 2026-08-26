import { Link } from 'react-router-dom'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import {
  CATEGORY_COLORS,
  CATEGORY_ORDER,
  CHART_INK,
  feedHref,
  fmtMoney,
  inOrder,
  pick,
  pivot,
} from '../../lib/market'

/**
 * What a bike of each type actually costs, as a distribution rather than an
 * average.
 *
 * Small multiples rather than five overlaid curves: the categories differ more
 * in shape than in height (commuters spike under $1k, road bikes run long), and
 * overlaying five filled areas hides exactly that. Every panel shares one x
 * scale so the panels are comparable by eye.
 */
export default function PriceDistribution({ points }) {
  const { rows, series } = pivot(pick(points, 'price_hist'))
  const medians = Object.fromEntries(
    pick(points, 'median_price').map((p) => [p.series, p]),
  )
  const categories = inOrder(series, CATEGORY_ORDER)

  return (
    <div>
      <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        {categories.map((category) => (
          <li key={category}>
            <Link
              to={feedHref({ category })}
              className="block rounded-xl border border-slate-200 bg-white p-3 hover:border-orange-400 transition"
            >
              <span className="flex items-center gap-1.5 text-xs text-slate-500">
                <span
                  aria-hidden="true"
                  className="inline-block h-2.5 w-2.5 rounded-[2px] ring-1 ring-black/5"
                  style={{ backgroundColor: CATEGORY_COLORS[category] }}
                />
                {category}
              </span>
              <span className="block text-lg font-semibold text-slate-900 mt-1 tabular-nums">
                {medians[category] ? fmtMoney(medians[category].value) : '–'}
              </span>
              <span className="block text-xs text-slate-400 tabular-nums">
                {(medians[category]?.n ?? 0).toLocaleString()} listings
              </span>
            </Link>
          </li>
        ))}
      </ul>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {categories.map((category) => (
          <Panel
            key={category}
            category={category}
            rows={rows}
            color={CATEGORY_COLORS[category]}
          />
        ))}
      </div>
    </div>
  )
}

function Panel({ category, rows, color }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-xs font-medium text-slate-600 mb-1">{category}</p>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={rows} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="bucket"
            tick={false}
            stroke={CHART_INK.axis}
            height={4}
          />
          <Tooltip content={<PriceTooltip category={category} />} cursor={{ fill: 'rgba(15,23,42,0.04)' }} />
          <Bar dataKey={category} isAnimationActive={false} radius={[2, 2, 0, 0]}>
            {rows.map((row) => (
              <Cell key={row.bucket} fill={color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="text-[10px] text-slate-400 flex justify-between mt-1">
        <span>{rows[0]?.bucket}</span>
        <span>{rows[rows.length - 1]?.bucket}</span>
      </p>
    </div>
  )
}

function PriceTooltip({ active, payload, label, category }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
      <div className="font-medium text-slate-900">{label}</div>
      <div className="text-slate-500">
        {payload[0].value.toLocaleString()} {category} listings
      </div>
    </div>
  )
}
