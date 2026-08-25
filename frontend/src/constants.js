export const REGIONS = [
  { name: 'Queensland',              abbr: 'QLD', cities: ['Brisbane', 'Gold Coast', 'Sunshine Coast', 'Toowoomba'] },
  { name: 'New South Wales',         abbr: 'NSW', cities: ['Sydney', 'Wollongong'] },
  { name: 'Australian Capital Territory', abbr: 'ACT', cities: ['Canberra'] },
  { name: 'Victoria',                abbr: 'VIC', cities: ['Melbourne'] },
  { name: 'South Australia',         abbr: 'SA',  cities: ['Adelaide'] },
  { name: 'Western Australia',       abbr: 'WA',  cities: ['Perth'] },
  { name: 'Northern Territory',      abbr: 'NT',  cities: [] },
  { name: 'Tasmania',                abbr: 'TAS', cities: ['Hobart'] },
]

// The canonical alpha scale the API emits, smallest first. Centimetre and inch
// sizes are not listed: they sort numerically and the API already returns the
// whole facet in scale order, so this is only a tiebreak for the client.
export const SIZE_ORDER = [
  'XXXS', 'XXS', 'XS', 'S', 'S/M', 'M', 'M/L', 'L', 'XL', 'XXL', 'XXXL',
]

export const DEFAULT_FILTERS = {
  category: [],
  city: [],
  size: [],
  vendor: [],
  brand: [],
  frame_material: [],
  drivetrain_groupset: [],
  min_discount: 0,
  min_price: '',
  max_price: '',
  q: '',
  added_since: '',
}
