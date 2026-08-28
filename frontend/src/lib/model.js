// What the card, table and detail page print for a bike's model, after the
// brand that every one of those views already shows beside it.
//
// Shops write the model field however they like, and many repeat the brand
// inside it: "Scott Contessa" (brand already shown), "2023 Scott Contessa"
// (brand mid-string, after a year), and even "Scott 2023 Scott Contessa"
// (twice). Since the listing views render `{brand} {model}`, each repeat reads
// as a stutter: "Scott 2023 Scott Contessa Genius 920". Measured against the
// live feed, about one card in five carried a duplicated brand this way.
//
// The fix is to drop every whole-word occurrence of the brand from the model
// and tidy the punctuation the removal strands. Model years are kept on
// purpose: a buyer uses them, so they are signal, not noise.
//
// Import-free (no JSX, no other modules) so the node --test runner can load it
// directly, the same arrangement as the other lib/ suites.

// Regex-escape the brand before it goes into a pattern. Brands are proper nouns,
// but a stray "." or "+" must match literally rather than as a metacharacter.
function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// Separator punctuation left dangling at an end once the brand is gone
// ("- Rail 9.9", "Contessa |"). The dashes and middot are written as escapes so
// no literal em dash appears in the source, per the repo's writing rule.
const EDGE_PUNCT = '[-:|/,\\u00b7\\u2013\\u2014]'
const STRIP_EDGE_PUNCT = new RegExp(`^${EDGE_PUNCT}+\\s*|\\s*${EDGE_PUNCT}+$`, 'g')

export function displayModelName(brand, modelName) {
  if (!modelName) return modelName || ''

  let out = modelName
  const trimmedBrand = (brand || '').trim()
  if (trimmedBrand) {
    // Whole-word and case-insensitive. A brand can be several words
    // ("Santa Cruz", "Rocky Mountain"), so match the phrase, not each token.
    out = out.replace(new RegExp(`\\b${escapeRegExp(trimmedBrand)}\\b`, 'gi'), ' ')
  }

  out = out.replace(/\s+/g, ' ').trim().replace(STRIP_EDGE_PUNCT, '').trim()

  // Never return empty: a model that was only the brand ("Trek") still needs a
  // label, so fall back to the raw value rather than rendering the brand alone.
  return out || modelName
}
