// The summary panel at the top of each guide: the four things someone skimming
// actually wants before they read a word of prose.
export default function AtAGlanceCard({ items }) {
  return (
    <dl className="bg-white border border-slate-200 rounded-xl p-6 grid gap-4 sm:grid-cols-2 my-6">
      {items.map(({ label, value }) => (
        <div key={label}>
          <dt className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
            {label}
          </dt>
          <dd className="text-sm text-slate-700 leading-relaxed">{value}</dd>
        </div>
      ))}
    </dl>
  )
}
