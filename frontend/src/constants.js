export const REGIONS = [
  { name: 'Queensland',              abbr: 'QLD', cities: ['Brisbane', 'Gold Coast', 'Sunshine Coast', 'Toowoomba'] },
  { name: 'New South Wales',         abbr: 'NSW', cities: ['Sydney', 'Wollongong'] },
  { name: 'Australian Capital Territory', abbr: 'ACT', cities: ['Canberra'] },
  { name: 'Victoria',                abbr: 'VIC', cities: ['Melbourne'] },
  { name: 'Western Australia',       abbr: 'WA',  cities: ['Perth'] },
  { name: 'Northern Territory',      abbr: 'NT',  cities: [] },
  { name: 'Tasmania',                abbr: 'TAS', cities: [] },
]

export const DEFAULT_FILTERS = {
  category: [],
  city: [],
  size: [],
  vendor: [],
  brand: [],
  min_discount: 0,
  q: '',
}
