// The applied filters, as a row of removable chips above the results.
//
// The sidebar already shows what is selected, but only if you look at it: on a
// phone it is a closed drawer, and on a desktop the selections are scattered
// down ten sections. The chip row is the answer to "why am I seeing 34 bikes
// and not 954", and every chip carries the update that removes it.
//
// Deliberately free of imports and JSX so the bare node test runner can load it.

function money(value) {
  const n = Number(value)
  return Number.isFinite(n) ? `$${n.toLocaleString('en-AU')}` : `$${value}`
}

const ADDED_SINCE_LABELS = {
  day: 'Added today',
  week: 'Added this week',
  month: 'Added this month',
  year: 'Added this year',
}

/**
 * Chips for everything currently narrowing the feed.
 *
 * Each chip is `{ key, label, clear }`, where `clear` is the params update that
 * removes just that one. The category pinned by the route is not a chip: it is
 * the page you are on, and the category bar is where you change it.
 */
export function activeChips(params) {
  const {
    category = [], city = [], size = [], vendor = [], brand = [],
    frame_material = [], drivetrain_groupset = [],
    min_discount = 0, min_price = '', max_price = '', q = '', added_since = '',
    lockedCategory = null,
  } = params ?? {}

  const chips = []

  const each = (key, values, label = (v) => v) => {
    for (const value of values) {
      chips.push({
        key: `${key}:${value}`,
        label: label(value),
        clear: { [key]: values.filter((v) => v !== value) },
      })
    }
  }

  if (!lockedCategory) each('category', category)
  each('city', city)
  each('size', size, (v) => `Size ${v}`)
  each('vendor', vendor)
  each('brand', brand)
  each('frame_material', frame_material)
  each('drivetrain_groupset', drivetrain_groupset)

  if (min_discount > 0) {
    chips.push({ key: 'min_discount', label: `${min_discount}% off or more`, clear: { min_discount: 0 } })
  }

  // One chip, not two: a range is a single idea, and clearing half of it leaves
  // a filter nobody asked for.
  if (min_price && max_price) {
    chips.push({
      key: 'price',
      label: `${money(min_price)} to ${money(max_price)}`,
      clear: { min_price: '', max_price: '' },
    })
  } else if (min_price) {
    chips.push({ key: 'price', label: `From ${money(min_price)}`, clear: { min_price: '' } })
  } else if (max_price) {
    chips.push({ key: 'price', label: `Under ${money(max_price)}`, clear: { max_price: '' } })
  }

  if (added_since) {
    chips.push({
      key: 'added_since',
      label: ADDED_SINCE_LABELS[added_since] ?? `Added in the last ${added_since}`,
      clear: { added_since: '' },
    })
  }

  if (q) chips.push({ key: 'q', label: `“${q}”`, clear: { q: '' } })

  return chips
}
