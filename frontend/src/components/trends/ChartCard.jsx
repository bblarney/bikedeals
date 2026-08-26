/**
 * The frame every chart on /trends sits in.
 *
 * One component rather than repeated markup because the honesty labelling is
 * part of the frame: `note` is where a chart says which subset it measured, and
 * a chart built on frame_material or drivetrain_groupset is not allowed to ship
 * without one.
 */
export default function ChartCard({ title, subtitle, note, legend, children }) {
  return (
    <section className="mb-10">
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
        {legend && <Legend items={legend} />}
        {children}
      </div>
      {note && <p className="text-xs text-slate-400 mt-2">{note}</p>}
    </section>
  )
}

/**
 * Always present for two or more series, so identity is never colour-alone.
 * Three of the palette's hues sit below 3:1 against white, which makes the
 * swatch-plus-name pairing load-bearing rather than decorative.
 */
export function Legend({ items }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 mb-3">
      {items.map(({ label, color }) => (
        <li key={label} className="flex items-center gap-1.5 text-xs text-slate-600">
          <span
            aria-hidden="true"
            className="inline-block h-2.5 w-2.5 rounded-[2px] ring-1 ring-black/5"
            style={{ backgroundColor: color }}
          />
          {label}
        </li>
      ))}
    </ul>
  )
}
