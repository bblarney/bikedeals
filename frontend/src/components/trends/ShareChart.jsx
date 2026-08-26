import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CHART_INK, fmtPct } from '../../lib/market'

/**
 * A 100%-stacked bar chart of composition across ordered buckets.
 *
 * Shared by the frame-material, drivetrain-brand and shifting charts because
 * all three ask the same question: of the listings in this bucket, what is the
 * mix? Shares rather than counts, so a bucket holding 3,000 cheap bikes and one
 * holding 200 superbikes are comparable at a glance.
 */
export default function ShareChart({ rows, series, colors, height = 280 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_INK.grid} vertical={false} />
        <XAxis
          dataKey="bucket"
          tick={{ fontSize: 11, fill: CHART_INK.tick }}
          stroke={CHART_INK.axis}
          interval={0}
        />
        <YAxis
          tickFormatter={fmtPct}
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: CHART_INK.tick }}
          stroke={CHART_INK.axis}
          width={40}
        />
        <Tooltip content={<ShareTooltip />} cursor={{ fill: 'rgba(15,23,42,0.04)' }} />
        {series.map((name) => (
          <Bar
            key={name}
            dataKey={name}
            stackId="share"
            fill={colors[name]}
            // A 2px gap between segments so adjacent fills read as separate
            // marks rather than one blended band.
            stroke="#ffffff"
            strokeWidth={2}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

function ShareTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const total = payload[0]?.payload?._total ?? 0
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
      <div className="font-medium text-slate-900">{label}</div>
      <div className="text-slate-400 mb-1">{total.toLocaleString()} listings</div>
      {[...payload].reverse().map((entry) => (
        <div key={entry.dataKey} className="flex items-center gap-1.5 text-slate-600">
          <span
            aria-hidden="true"
            className="inline-block h-2 w-2 rounded-[2px]"
            style={{ backgroundColor: entry.color }}
          />
          <span className="flex-1">{entry.dataKey}</span>
          <span className="font-medium text-slate-900 tabular-nums">
            {fmtPct(entry.value)}
          </span>
          <span className="text-slate-400 tabular-nums">
            ({entry.payload[`${entry.dataKey}_n`]?.toLocaleString() ?? 0})
          </span>
        </div>
      ))}
    </div>
  )
}
