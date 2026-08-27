import { useQuery } from '@tanstack/react-query'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api/client'
import { formatShortDate } from '../lib/time'

const SALE_COLOR = '#ea580c' // orange-600
const RRP_COLOR = '#cbd5e1' // slate-300

const fmtMoney = (v) => `$${Math.round(v).toLocaleString()}`
const fmtAxisDate = (ms) => formatShortDate(new Date(ms))

// Recharts wants numeric x-values for a true time axis. We also append a
// synthetic point at "now" using the bike's current price so the final step
// extends to today (events only exist at the moments price changed).
function buildSeries(events, bike) {
  const points = events.map((e) => ({
    t: new Date(e.observed_at).getTime(),
    price_sale: e.price_sale,
    price_original: e.price_original ?? null,
  }))
  const lastT = points[points.length - 1].t
  const nowT = Date.now()
  if (nowT > lastT) {
    points.push({ t: nowT, price_sale: bike.price_sale, price_original: bike.price_original ?? null })
  }
  return points
}

function PriceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const sale = payload.find((p) => p.dataKey === 'price_sale')
  const rrp = payload.find((p) => p.dataKey === 'price_original')
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
      <div className="font-medium text-slate-500">{fmtAxisDate(label)}</div>
      {sale && <div className="font-semibold text-slate-900">{fmtMoney(sale.value)}</div>}
      {rrp && rrp.value != null && (
        <div className="text-slate-400">RRP {fmtMoney(rrp.value)}</div>
      )}
    </div>
  )
}

export default function PriceHistoryChart({ id, bike }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['price-history', id],
    queryFn: () => api.getPriceHistory(id),
    staleTime: 5 * 60 * 1000,
  })

  // Hide entirely while loading or on error — it's a secondary enhancement,
  // not core to the page.
  if (isLoading || isError || !data) return null

  // A single event (first seen, never changed) is a flat line, and drawing one
  // implies a trend that is not there. Say what we actually know instead: most
  // listings are one observation deep, and "no change since we started
  // watching" is a real answer, where "unavailable" was not.
  if (data.length < 2) {
    const since = data.length === 1 ? formatShortDate(new Date(data[0].observed_at)) : null
    return (
      <section className="mt-12">
        <h2 className="text-lg font-bold text-slate-900 tracking-tight mb-1">Price history</h2>
        <p className="text-sm text-slate-500">
          {since
            ? `Tracked since ${since}. The price has not moved since we first saw it.`
            : 'We have not recorded a price change for this listing yet.'}
        </p>
      </section>
    )
  }

  const series = buildSeries(data, bike)
  const hasRrp = series.some((p) => p.price_original != null)

  return (
    <section className="mt-12">
      <h2 className="text-lg font-bold text-slate-900 tracking-tight mb-1">Price history</h2>
      <p className="text-sm text-slate-500 mb-4">Sale price since we started tracking this listing.</p>
      <div className="rounded-xl border border-slate-200 p-4">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={series} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              tickFormatter={fmtAxisDate}
              tick={{ fontSize: 12, fill: '#94a3b8' }}
              stroke="#e2e8f0"
            />
            <YAxis
              tickFormatter={fmtMoney}
              tick={{ fontSize: 12, fill: '#94a3b8' }}
              stroke="#e2e8f0"
              width={56}
              domain={['auto', 'auto']}
            />
            <Tooltip content={<PriceTooltip />} />
            {hasRrp && (
              <Line
                type="stepAfter"
                dataKey="price_original"
                stroke={RRP_COLOR}
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            )}
            <Line
              type="stepAfter"
              dataKey="price_sale"
              stroke={SALE_COLOR}
              strokeWidth={2}
              dot={{ r: 2, fill: SALE_COLOR }}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
