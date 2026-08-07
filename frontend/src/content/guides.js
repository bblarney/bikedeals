// The guide index. Drives the hub's card grid, GuideLayout's cross-links,
// SitemapPage, and the ROUTES list in scripts/prerender.js, so a new guide
// cannot be added without also being prerendered. An unlisted route 404s in
// production (see public/_redirects).
//
// Deliberately dependency-free: prerender.js imports this with bare `node`,
// outside Vite. No JSX, no imports, no import.meta.env. In particular do not
// import seo.js, which reads import.meta.env.VITE_PUBLIC_URL.

export const GUIDES = [
  {
    slug: 'electric-bikes',
    path: '/guides/electric-bikes',
    label: 'Electric bikes',
    category: 'E-Bike',
    title: 'Electric Bike Guide: Types, Costs and Who They Suit · BikeGrid',
    description:
      'What an e-bike is, how cargo, e-MTB, electric road and city e-bikes differ, what they cost in Australia and how to pick one. With live deals from local shops.',
    heading: 'The electric bike guide',
    cardBlurb:
      'Cargo, e-MTB, electric road, city. What the four kinds of e-bike are for, what they cost, and how the law works in Australia.',
  },
  {
    slug: 'mountain-bikes',
    path: '/guides/mountain-bikes',
    label: 'Mountain bikes',
    category: 'Mountain',
    title: 'Mountain Bike Guide: Hardtail vs Full Suspension · BikeGrid',
    description:
      'What makes a mountain bike a mountain bike, the difference between hardtail and full suspension, which trails suit which bike, and what to spend. With live deals.',
    heading: 'The mountain bike guide',
    cardBlurb:
      'Suspension, fat tyres, flat bars. Built to be ridden down things. Includes hardtail vs full suspension.',
  },
  {
    slug: 'road-bikes',
    path: '/guides/road-bikes',
    label: 'Road bikes',
    category: 'Road',
    title: 'Road Bike Guide: Who They Suit and What to Spend · BikeGrid',
    description:
      'Why road bikes are shaped the way they are, what drop bars and skinny tyres do for you, who they suit, and what you get at each price. With live deals.',
    heading: 'The road bike guide',
    cardBlurb:
      'Drop bars and skinny tyres, built for sealed roads and distance. The fastest way to cover ground under your own power.',
  },
  {
    slug: 'gravel-bikes',
    path: '/guides/gravel-bikes',
    label: 'Gravel bikes',
    category: 'Gravel',
    title: 'Gravel Bike Guide: The Do-Everything Bike · BikeGrid',
    description:
      'What a gravel bike is, how it differs from a road bike and a mountain bike, and why it suits riders who want one bike for mixed surfaces. With live deals.',
    heading: 'The gravel bike guide',
    cardBlurb:
      'A road bike with room for wider tyres and rougher ground. If you can only own one bike, it is probably this one.',
  },
  {
    slug: 'commuter-bikes',
    path: '/guides/commuter-bikes',
    label: 'Commuter & city bikes',
    category: 'Commuter',
    title: 'Commuter Bike Guide: Getting Around Town · BikeGrid',
    description:
      'Flat-bar hybrids, city bikes, folding bikes and kids bikes. What to look for in a bike you ride in normal clothes, and what actually matters. With live deals.',
    heading: 'The commuter bike guide',
    cardBlurb:
      'Upright, practical, ridden in normal clothes. Hybrids, city bikes and folders, for replacing short car trips.',
  },
]

export const GUIDE_PATHS = ['/guides', ...GUIDES.map((g) => g.path)]
