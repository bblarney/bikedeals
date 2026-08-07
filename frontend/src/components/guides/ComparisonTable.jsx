// A small comparison grid. Wrapped in overflow-x-auto so a five-column table
// scrolls inside its own box on a phone instead of pushing the page sideways.
export default function ComparisonTable({ columns, rows, caption }) {
  return (
    <div className="my-6">
      <div className="overflow-x-auto border border-slate-200 rounded-xl bg-white">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-slate-200">
              <th scope="col" className="text-left font-semibold text-slate-800 px-4 py-3 whitespace-nowrap">
                {columns[0]}
              </th>
              {columns.slice(1).map((c) => (
                <th key={c} scope="col" className="text-left font-semibold text-slate-800 px-4 py-3 whitespace-nowrap">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row[0]} className="border-b border-slate-100 last:border-0 align-top">
                <th scope="row" className="text-left font-medium text-slate-700 px-4 py-3 whitespace-nowrap">
                  {row[0]}
                </th>
                {row.slice(1).map((cell, i) => (
                  <td key={i} className="text-slate-600 px-4 py-3 leading-relaxed">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {caption && <p className="text-xs text-slate-400 mt-2">{caption}</p>}
    </div>
  )
}
