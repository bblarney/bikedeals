import { Link } from 'react-router-dom'
import { GROUPSET_BRAND_COLORS, groupsetBrand, pick } from '../../lib/market'

/**
 * Every groupset on the market, ranked by how many listings carry it.
 *
 * Ordered by volume rather than by tier: a tier ladder would need a ranking the
 * API does not publish and the two brands' tiers do not cleanly interleave, so
 * ordering by what shops actually stock says more and invents nothing. Colour
 * carries the brand, which is the comparison the chart exists for.
 */
export default function GroupsetLadder({ points }) {
  const rows = pick(points, 'groupset_ladder')
    .map((p) => ({ name: p.series, n: p.n, brand: groupsetBrand(p.series) }))
    .sort((a, b) => b.n - a.n || a.name.localeCompare(b.name))
  if (!rows.length) return null
  const max = Math.max(...rows.map((r) => r.n))

  return (
    <ol className="space-y-1 max-h-[28rem] overflow-y-auto pr-1">
      {rows.map((row) => (
        <li key={row.name}>
          <Link
            to={`/?drivetrain_groupset=${encodeURIComponent(row.name)}`}
            className="group grid grid-cols-[9rem_1fr_auto] sm:grid-cols-[12rem_1fr_auto] items-center gap-3 rounded-lg px-2 py-1 hover:bg-slate-50 transition"
          >
            <span className="text-xs text-slate-600 truncate group-hover:text-orange-600">
              {row.name}
            </span>
            <span
              className="h-3 rounded-[3px]"
              style={{
                width: `${Math.max((row.n / max) * 100, 1)}%`,
                backgroundColor: GROUPSET_BRAND_COLORS[row.brand] ?? '#94a3b8',
              }}
            />
            <span className="text-xs text-slate-500 tabular-nums w-12 text-right">
              {row.n.toLocaleString()}
            </span>
          </Link>
        </li>
      ))}
    </ol>
  )
}
