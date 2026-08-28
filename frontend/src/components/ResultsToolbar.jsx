import { activeChips } from '../lib/chips'
import { formatDayLabel } from '../lib/time'

// Dollars off and percent off are different questions, so they are different
// sorts: 20% off a $13,000 bike is $2,600, and 60% off a $600 one is $360.
const SORT_LABELS = {
  discount_desc: 'Deepest discount',
  saving_desc: 'Biggest saving',
  price_asc: 'Price: low to high',
  price_desc: 'Price: high to low',
  clicks_desc: 'Most popular',
}

export default function ResultsToolbar({
  total,
  shopCount,
  lastScrapedAt,
  newToday,
  isFetching,
  params,
  onUpdate,
  savedCount = 0,
  onClearSaved,
}) {
  const { sort, view } = params
  const chips = activeChips(params)
  const updated = lastScrapedAt ? formatDayLabel(new Date(lastScrapedAt)) : null

  return (
    <div className="bg-navy-800 border-b border-white/10">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5">
        <p className="text-sm text-slate-300 flex items-center gap-2">
          {isFetching && <Spinner />}
          {total != null ? (
            <>
              <b className="tabular-nums text-base font-semibold text-white">
                {total.toLocaleString()}
              </b>
              result{total === 1 ? '' : 's'}
              {shopCount ? ` from ${shopCount} shop${shopCount === 1 ? '' : 's'}` : ''}
            </>
          ) : (
            <span className="text-slate-500">Loading…</span>
          )}
        </p>

        {updated && (
          <span className="text-[11px] text-slate-500 hidden sm:inline">updated {updated}</span>
        )}
        {newToday > 0 && (
          <span className="text-[11px] font-bold text-orange-300 bg-orange-500/20 px-2 py-0.5 rounded-full">
            {newToday} new today
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="hidden sm:inline">Sort</span>
            <select
              value={sort}
              onChange={(e) => onUpdate({ sort: e.target.value })}
              aria-label="Sort results"
              className="select-dark border border-white/15 rounded-lg px-2 py-1 text-xs font-semibold text-white bg-white/5 cursor-pointer focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition"
            >
              {Object.entries(SORT_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>

          {/* Cards are for browsing, the table is for comparing. Same query, same
              filters, one toggle: the data was always tabular. */}
          <div className="flex border border-white/15 rounded-lg overflow-hidden" role="group" aria-label="Result layout">
            <ViewButton current={view} value="grid" onUpdate={onUpdate} label="Grid">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
              </svg>
            </ViewButton>
            <ViewButton current={view} value="table" onUpdate={onUpdate} label="Table">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M3 6h18M3 12h18M3 18h18" />
              </svg>
            </ViewButton>
          </div>
        </div>
      </div>

      {(chips.length > 0 || savedCount > 0) && (
        <div className="flex flex-wrap items-center gap-1.5 px-4 py-2 border-t border-white/10 bg-navy-900">
          {chips.map((chip) => (
            <button
              key={chip.key}
              onClick={() => onUpdate(chip.clear)}
              className="group inline-flex items-center gap-1.5 border border-white/15 bg-white/5 rounded-lg pl-2.5 pr-2 py-1 text-xs text-slate-200 hover:border-white/30 transition-colors"
            >
              <span className="font-semibold">{chip.label}</span>
              <span aria-hidden="true" className="text-slate-500 group-hover:text-white">&times;</span>
              <span className="sr-only">Remove filter</span>
            </button>
          ))}
          {chips.length > 1 && (
            <button
              onClick={() => onUpdate(CLEARED)}
              className="ml-1 text-xs font-bold text-orange-400 hover:text-orange-300"
            >
              Clear all
            </button>
          )}
          {savedCount > 0 && (
            <button
              onClick={onClearSaved}
              className="ml-auto inline-flex items-center gap-1.5 text-xs text-slate-300 hover:text-white"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" className="text-orange-400">
                <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21.2l7.8-7.8 1-1.1a5.5 5.5 0 0 0 0-7.7z" />
              </svg>
              {savedCount} saved
              <span className="text-slate-500">&times;</span>
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// Everything the chip row can clear. Not DEFAULT_FILTERS: that also resets the
// category, and on /gravel-bikes the category is the page.
const CLEARED = {
  city: [], size: [], vendor: [], brand: [], frame_material: [],
  drivetrain_groupset: [], min_discount: 0, min_price: '', max_price: '',
  q: '', added_since: '',
}

function ViewButton({ current, value, onUpdate, label, children }) {
  const on = current === value
  return (
    <button
      type="button"
      onClick={() => onUpdate({ view: value })}
      aria-pressed={on}
      title={`${label} view`}
      className={`flex items-center gap-1.5 px-2 py-1 text-xs transition-colors ${
        on ? 'bg-orange-500 text-white font-semibold' : 'bg-white/5 text-slate-400 hover:text-white'
      }`}
    >
      {children}
      <span className="hidden lg:inline">{label}</span>
    </button>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin text-orange-400 flex-shrink-0" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M12 2a10 10 0 0 1 10 10" />
    </svg>
  )
}
