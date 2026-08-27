import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { isHttpUrl } from '../lib/urls'

// Cards are for browsing; comparing is a table job and the data was always
// tabular. Nine bikes fit where four cards did, and the saving in dollars sits
// next to the discount in percent because those two rank differently and the
// difference is the point.
const money = (n) => `$${Math.round(n).toLocaleString('en-AU')}`

function listedOn(iso) {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })
}

// Which sort each sortable column asks for. Price toggles direction because
// "cheapest first" and "dearest first" are both real questions; the others have
// only one useful direction.
function sortFor(column, current) {
  if (column === 'now') return current === 'price_asc' ? 'price_desc' : 'price_asc'
  if (column === 'save') return 'saving_desc'
  if (column === 'off') return 'discount_desc'
  return null
}

const SORTED_BY = {
  price_asc: 'now',
  price_desc: 'now',
  saving_desc: 'save',
  discount_desc: 'off',
}

export default function BikeTable({ bikes, params, onUpdate, pinnedIds, onTogglePin }) {
  const navigate = useNavigate()

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[62rem] border-collapse text-xs">
        <thead>
          <tr>
            <Th>Bike</Th>
            <Th>Spec</Th>
            <Th>Sizes</Th>
            <Th>Shop</Th>
            <Th>Listed</Th>
            <Th right>Was</Th>
            <Th right column="now" params={params} onUpdate={onUpdate}>Now</Th>
            <Th right column="save" params={params} onUpdate={onUpdate}>Save</Th>
            <Th right column="off" params={params} onUpdate={onUpdate}>Off</Th>
            <Th><span className="sr-only">Actions</span></Th>
          </tr>
        </thead>
        <tbody>
          {bikes.map((bike) => (
            <Row
              key={bike.id}
              bike={bike}
              isPinned={pinnedIds.has(bike.id)}
              onTogglePin={onTogglePin}
              onOpen={() => navigate(`/bikes/${bike.id}`)}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Th({ children, right = false, column = null, params, onUpdate }) {
  const base = `tabular-nums text-[9.5px] uppercase tracking-[0.12em] text-slate-400 font-medium
    px-3 py-2.5 border-b border-slate-200 bg-slate-50 whitespace-nowrap ${right ? 'text-right' : 'text-left'}`

  if (!column) return <th scope="col" className={base}>{children}</th>

  const isSorted = SORTED_BY[params.sort] === column
  return (
    <th scope="col" className={base} aria-sort={isSorted ? 'descending' : 'none'}>
      <button
        type="button"
        onClick={() => onUpdate({ sort: sortFor(column, params.sort) })}
        className={`inline-flex items-center gap-1 hover:text-slate-700 transition-colors ${isSorted ? 'text-slate-900' : ''}`}
      >
        {children}
        <span aria-hidden="true" className={isSorted ? 'text-orange-600' : 'text-slate-300'}>
          {params.sort === 'price_asc' && column === 'now' ? '↑' : '↓'}
        </span>
      </button>
    </th>
  )
}

function Row({ bike, isPinned, onTogglePin, onOpen }) {
  const {
    brand, model_name, frame_material, drivetrain_groupset, sizes = [],
    frame_size_canonical, vendor_name, city, location_count = 1,
    sku_vendor_count = 0, scraped_at, price_original, price_sale,
    discount_percentage, product_url, image_url,
  } = bike

  const safeProductUrl = isHttpUrl(product_url) ? product_url : null
  const safeImageUrl = isHttpUrl(image_url) ? image_url : null
  const saving = price_original && price_original > price_sale ? price_original - price_sale : 0
  const spec = [frame_material, drivetrain_groupset].filter(Boolean).join(' · ')
  // frame_size_canonical is null when the shop's own size names nothing
  // usable ("N/A", "One Size"), which is exactly when there is nothing to show.
  const sizeList = sizes.length > 0 ? sizes : [frame_size_canonical].filter(Boolean)
  const listed = listedOn(scraped_at)

  const cell = 'px-3 py-2 border-b border-slate-100 align-middle text-slate-600'

  return (
    <tr
      onClick={onOpen}
      className="cursor-pointer hover:bg-slate-50/80 transition-colors"
    >
      <td className={cell}>
        <div className="flex items-center gap-2.5">
          <span className="w-11 h-8 flex-shrink-0 bg-slate-50 rounded flex items-center justify-center overflow-hidden">
            {safeImageUrl ? (
              <img src={safeImageUrl} alt="" loading="lazy" className="w-full h-full object-contain mix-blend-multiply" />
            ) : (
              <BikeGlyph className="text-slate-300" />
            )}
          </span>
          <span className="min-w-0">
            <span className="block tabular-nums text-[9.5px] uppercase tracking-[0.1em] text-slate-400 truncate">{brand}</span>
            <Link
              to={`/bikes/${bike.id}`}
              onClick={(e) => e.stopPropagation()}
              className="block text-[13px] font-bold text-slate-900 leading-tight hover:text-orange-600 line-clamp-1"
            >
              {model_name}
            </Link>
          </span>
        </div>
      </td>

      <td className={cell}>
        {spec || <span className="text-slate-300">not published</span>}
      </td>

      <td className={`${cell} tabular-nums`}>
        {sizeList.length > 0 ? sizeList.join(' ') : <span className="text-slate-300">n/a</span>}
      </td>

      <td className={cell}>
        <span className="truncate block max-w-[11rem]">{vendor_name}{city ? `, ${city}` : ''}</span>
        {sku_vendor_count >= 2 && (
          <span className="tabular-nums text-[10px] font-semibold text-emerald-700 bg-emerald-50 rounded px-1.5 py-px inline-block mt-0.5">
            {sku_vendor_count} shops
          </span>
        )}
        {location_count > 1 && (
          <span className="tabular-nums text-[10px] text-slate-400 ml-1">+{location_count - 1} stores</span>
        )}
      </td>

      <td className={`${cell} tabular-nums text-slate-400 whitespace-nowrap`}>{listed ?? ''}</td>

      <td className={`${cell} text-right tabular-nums text-slate-400 line-through`}>
        {price_original && price_original > price_sale ? money(price_original) : ''}
      </td>

      <td className={`${cell} text-right tabular-nums text-[13px] font-semibold text-slate-900`}>
        {money(price_sale)}
      </td>

      <td className={`${cell} text-right tabular-nums text-emerald-700`}>
        {saving > 0 ? money(saving) : ''}
      </td>

      <td className={`${cell} text-right`}>
        {discount_percentage > 0 && (
          <span className="tabular-nums font-semibold text-orange-700 bg-orange-50 rounded px-1.5 py-0.5">
            {discount_percentage}%
          </span>
        )}
      </td>

      <td className={`${cell} text-right whitespace-nowrap`}>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onTogglePin(bike) }}
          aria-label={isPinned ? 'Remove from saved' : 'Save deal'}
          aria-pressed={isPinned}
          className={`align-middle mr-2 ${isPinned ? 'text-orange-600' : 'text-slate-300 hover:text-orange-500'}`}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill={isPinned ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
          </svg>
        </button>
        <a
          href={safeProductUrl ?? undefined}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => { e.stopPropagation(); if (!safeProductUrl) { e.preventDefault(); return } api.recordClick(bike.id) }}
          className="text-orange-600 hover:text-orange-700 font-bold"
        >
          View
        </a>
      </td>
    </tr>
  )
}

function BikeGlyph({ className }) {
  return (
    <svg width="30" height="19" viewBox="0 0 64 40" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="14" cy="28" r="10" /><circle cx="50" cy="28" r="10" />
      <path d="M14 28 27 12h16M27 12l5 16M32 28 43 12M32 28h18M24 11h7M40 9h7" />
    </svg>
  )
}
