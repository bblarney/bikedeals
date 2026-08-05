// Flat 2D Australian flag, drawn to the official 1:2 geometry
// (canvas is 10080x5040 so star positions match the spec exactly).

const NAVY = '#00247D'
const RED = '#CC142B'
const WHITE = '#FFFFFF'

// Stars are 7-pointed (except Epsilon Crucis), inner radius 4/9 of outer.
function star(cx, cy, outer, points) {
  const inner = (outer * 4) / 9
  const step = Math.PI / points
  let d = ''
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? outer : inner
    const a = -Math.PI / 2 + i * step
    d += `${i ? 'L' : 'M'}${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`
  }
  return `${d}Z`
}

const SOUTHERN_CROSS = [
  [7560, 4200, 360, 7], // Alpha Crucis
  [6300, 2205, 360, 7], // Beta Crucis
  [7560, 1470, 360, 7], // Gamma Crucis
  [8680, 2205, 360, 7], // Delta Crucis
  [8064, 3192, 210, 5], // Epsilon Crucis
]

export default function FlagAU({ className = '' }) {
  return (
    <svg
      viewBox="0 0 10080 5040"
      className={className}
      role="img"
      aria-label="Australia"
      preserveAspectRatio="xMidYMid meet"
    >
      <rect width="10080" height="5040" fill={NAVY} />

      {/* Union Jack canton — top hoist quarter */}
      <svg x="0" y="0" width="5040" height="2520" viewBox="0 0 60 30">
        <clipPath id="flag-au-canton">
          <path d="M0,0 v30 h60 v-30 z" />
        </clipPath>
        <clipPath id="flag-au-saltire">
          <path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" />
        </clipPath>
        <g clipPath="url(#flag-au-canton)">
          <path d="M0,0 v30 h60 v-30 z" fill={NAVY} />
          <path d="M0,0 L60,30 M60,0 L0,30" stroke={WHITE} strokeWidth="6" />
          <path
            d="M0,0 L60,30 M60,0 L0,30"
            clipPath="url(#flag-au-saltire)"
            stroke={RED}
            strokeWidth="4"
          />
          <path d="M30,0 v30 M0,15 h60" stroke={WHITE} strokeWidth="10" />
          <path d="M30,0 v30 M0,15 h60" stroke={RED} strokeWidth="6" />
        </g>
      </svg>

      {/* Commonwealth Star */}
      <path d={star(2520, 3780, 756, 7)} fill={WHITE} />

      {/* Southern Cross */}
      {SOUTHERN_CROSS.map(([cx, cy, r, p]) => (
        <path key={`${cx}-${cy}`} d={star(cx, cy, r, p)} fill={WHITE} />
      ))}
    </svg>
  )
}
