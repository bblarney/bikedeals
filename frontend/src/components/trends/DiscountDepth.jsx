import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CHART_INK, pick } from '../../lib/market'

const BAR_COLOR = '#ea580c' // orange-600, the site accent

/**
 * How deep the discounts run, across every listing currently on sale.
 *
 * A single series, so no legend: the title names it. Bars carry their own
 * counts, which is what makes the round-number clustering (shops price at 20%,
 * 30%, 40%, rarely at 23%) visible rather than merely implied by the shape.
 */
export default function DiscountDepth({ points }) {
  const rows = pick(points, 'discount_hist').map((p) => ({ bucket: p.bucket, n: p.n }))
  if (!rows.length) return null

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={rows} margin={{ top: 16, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_INK.grid} vertical={false} />
        <XAxis
          dataKey="bucket"
          tick={{ fontSize: 11, fill: CHART_INK.tick }}
          stroke={CHART_INK.axis}
          interval={0}
        />
        <YAxis
          tick={{ fontSize: 11, fill: CHART_INK.tick }}
          stroke={CHART_INK.axis}
          width={48}
          tickFormatter={(v) => v.toLocaleString()}
        />
        <Tooltip content={<DepthTooltip />} cursor={{ fill: 'rgba(15,23,42,0.04)' }} />
        <Bar dataKey="n" fill={BAR_COLOR} radius={[4, 4, 0, 0]} isAnimationActive={false}>
          <LabelList
            dataKey="n"
            position="top"
            fontSize={11}
            fill={CHART_INK.label}
            formatter={(v) => v.toLocaleString()}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function DepthTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
      <div className="font-medium text-slate-900">{label} off</div>
      <div className="text-slate-500">{payload[0].value.toLocaleString()} listings</div>
    </div>
  )
}
