// Where the visitor's region is remembered.
//
// This used to be a gate: `/` rendered a full-page region picker for a
// first-time visitor and the deal feed for everyone else, which meant the
// highest-authority URL on the site had no content on it, and returning
// visitors watched the landing markup get replaced on every refresh. Region is
// a filter, so it is now a control in the header (see RegionMenu) and `/` is a
// real page.
//
// The remembering survived the gate: a visitor who picked Victoria last week
// should land on Victorian deals, without being asked again.
//
// Bare `node` loads this file from scripts/prerender.js, outside Vite: no JSX,
// no imports, no `import.meta.env`.

export const REGION_KEY = 'bikegrid_region'

// '__all__' is a real answer, not a missing one: it means the visitor chose all
// of Australia and should not be narrowed on the next visit either.
export const ALL_REGIONS = '__all__'

// Guarded because this also runs during the build-time prerender, where there
// is no localStorage, and in a browser that blocks storage access entirely.
export function storedRegion() {
  try {
    return localStorage.getItem(REGION_KEY)
  } catch {
    return null
  }
}
