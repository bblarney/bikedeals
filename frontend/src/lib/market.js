// Shared vocabulary for the /trends charts: the palette, the reshaping helpers
// that turn the API's flat point list into per-chart tables, and the two
// derivations the API deliberately leaves to the client.
//
// The palette is one module rather than per-component constants because the
// page shows seven charts and a colour that means "Carbon" in one of them must
// not mean "Road" in the next. Every set below was run through the data-viz
// validator against this site's white chart surface; the ordering is the
// colourblind-safety mechanism, so add slots at the end rather than reordering.
// Three of the hues sit below 3:1 contrast on white, which is why every chart
// here ships a legend and visible labels rather than leaning on colour alone.

const SLOT = {
  blue: '#2a78d6',
  orange: '#eb6834',
  aqua: '#1baf7a',
  yellow: '#eda100',
  magenta: '#e87ba4',
  red: '#e34948',
}

// Fixed assignment, never cycled: a filter that drops a series must not repaint
// the survivors.
export const CATEGORY_COLORS = {
  Commuter: SLOT.blue,
  'E-Bike': SLOT.orange,
  Mountain: SLOT.aqua,
  Gravel: SLOT.yellow,
  Road: SLOT.magenta,
}

export const MATERIAL_COLORS = {
  Carbon: SLOT.blue,
  Aluminium: SLOT.orange,
  Steel: SLOT.aqua,
  Titanium: SLOT.yellow,
}

// The one place a hue is chosen for meaning rather than for slot order: these
// are the colours the componentry itself wears, so a rider reads them faster
// than any legend. Validated as an all-pairs set, not just adjacent.
export const GROUPSET_BRAND_COLORS = {
  Shimano: SLOT.blue,
  SRAM: SLOT.red,
  Campagnolo: SLOT.yellow,
}

export const SHIFTING_COLORS = {
  Electronic: SLOT.blue,
  Mechanical: SLOT.orange,
}

// One hue, light to dark, for continuous magnitude. The lightest step is
// allowed to recede toward the surface because it means "near zero".
export const DISCOUNT_RAMP = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#104281']

export const CHART_INK = {
  grid: '#f1f5f9',      // slate-100
  axis: '#e2e8f0',      // slate-200
  tick: '#94a3b8',      // slate-400
  label: '#475569',     // slate-600
}

export const CATEGORY_ORDER = ['Commuter', 'E-Bike', 'Mountain', 'Gravel', 'Road']

export const fmtMoney = (v) => `$${Math.round(v).toLocaleString()}`
export const fmtPct = (v) => `${Math.round(v)}%`

/** Every point belonging to one chart, in the order the API emitted them. */
/**
 * The two enrichment fields, as the percentage of listings that publish them.
 *
 * Frame material and groupset are only as good as what the shops put in their
 * feeds, and filtering by either hides every listing that says nothing. The
 * filter rail prints these next to those two controls so narrowing by them is
 * an informed choice rather than a surprise.
 */
export function coverageShares(data) {
  const total = data?.total_listings
  const coverage = data?.coverage
  if (!total || !coverage) return null
  const share = (n) => (typeof n === 'number' ? Math.round((n / total) * 100) : null)
  return {
    frame_material: share(coverage.frame_material),
    drivetrain_groupset: share(coverage.drivetrain_groupset),
  }
}

export function pick(points, chart) {
  return points.filter((p) => p.chart === chart)
}

/**
 * Flat points to a recharts row table: one row per bucket, one key per series.
 *
 * Bucket order comes from the API's bucket_rank and series order from the order
 * the points arrive in, so neither is duplicated as a constant here. Missing
 * combinations become 0 rather than undefined, or a stacked bar leaves a hole
 * where a segment should be.
 */
export function pivot(points) {
  const seriesNames = []
  const byBucket = new Map()
  for (const p of points) {
    if (!seriesNames.includes(p.series)) seriesNames.push(p.series)
    if (!byBucket.has(p.bucket)) byBucket.set(p.bucket, { bucket: p.bucket, _total: 0 })
    const row = byBucket.get(p.bucket)
    row[p.series] = (row[p.series] ?? 0) + p.n
    row._total += p.n
  }
  const rows = [...byBucket.values()]
  for (const row of rows) {
    for (const name of seriesNames) row[name] = row[name] ?? 0
  }
  return { rows, series: seriesNames }
}

/**
 * The same table as percentages of each bucket's total.
 *
 * Shares rather than counts is the whole point of these charts: the catalogue
 * has ten times as many bikes under $2k as over $8k, so raw stacked counts
 * would say nothing except "cheap bikes are common".
 */
export function toShares({ rows, series }) {
  return {
    series,
    rows: rows.map((row) => {
      const out = { bucket: row.bucket, _total: row._total }
      for (const name of series) {
        out[name] = row._total ? (row[name] / row._total) * 100 : 0
        out[`${name}_n`] = row[name]
      }
      return out
    }),
  }
}

/** Sort a series list into a fixed display order, unknown names last. */
export function inOrder(series, order) {
  return [...series].sort((a, b) => {
    const ai = order.indexOf(a)
    const bi = order.indexOf(b)
    return (ai < 0 ? order.length : ai) - (bi < 0 ? order.length : bi)
  })
}

// The API ships the groupset series already rolled up, both to brand and to
// electronic-versus-mechanical, so the only splitting left here is reading the
// brand off a ladder row to colour it. The string's shape is guaranteed by the
// scraper's normaliser.
export function groupsetBrand(name) {
  return name.split(' ')[0]
}

/**
 * A link into the feed with the same filters the chart segment represents.
 *
 * Price bands are the one lossy case: the feed takes numeric bounds, so the
 * band's own label is parsed back into them here rather than shipped twice.
 */
export function feedHref({ category, brand, frame_material, band } = {}) {
  const params = new URLSearchParams()
  if (category) params.append('category', category)
  if (brand) params.append('brand', brand)
  if (frame_material) params.append('frame_material', frame_material)
  const bounds = band && BAND_BOUNDS[band]
  if (bounds) {
    if (bounds[0] != null) params.set('min_price', String(bounds[0]))
    if (bounds[1] != null) params.set('max_price', String(bounds[1]))
  }
  const qs = params.toString()
  return qs ? `/?${qs}` : '/'
}

// Mirrors _PRICE_BANDS in api/main.py. Duplicated deliberately and kept small:
// the API owns the bucketing and its labels, this only maps a label back to the
// bounds the feed's own filters take.
const BAND_BOUNDS = {
  'Under $1k': [null, 1000],
  '$1–2k': [1000, 2000],
  '$2–3k': [2000, 3000],
  '$3–5k': [3000, 5000],
  '$5–8k': [5000, 8000],
  '$8–12k': [8000, 12000],
  '$12k+': [12000, null],
}
