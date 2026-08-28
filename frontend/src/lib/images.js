// Ask Shopify's image CDN for a display-sized copy instead of the full-res
// original.
//
// 98% of our product images are on cdn.shopify.com, and none of the scraped
// URLs carry a size, so every card was downloading a 1-3 MB photo to paint a
// slot a few hundred pixels wide. The CDN resizes on the fly from a `width`
// query parameter: a 2.3 MB hero comes back at ~170 KB for a 600px card and
// ~10 KB for a 120px table thumbnail, keeping the aspect ratio and returning
// JPEG.
//
// Only cdn.shopify.com is rewritten. The other ~2% of images sit on assorted
// vendor CDNs with no shared transform contract, so those pass through
// untouched. Anything that is not a valid http(s) URL is returned unchanged;
// callers still guard with isHttpUrl before rendering.
//
// Import-free (no JSX, no other modules) so the node --test runner can load it
// directly, the same arrangement as the other lib/ suites.

export function shopImage(url, width) {
  if (!url) return url
  try {
    const u = new URL(url)
    // Scoped to the one host whose transform contract we know. searchParams.set
    // handles both a bare URL and one that already carries Shopify's ?v= cache
    // key, and overwrites any width already present rather than appending a
    // second one.
    if (u.hostname !== 'cdn.shopify.com') return url
    u.searchParams.set('width', String(width))
    return u.toString()
  } catch {
    return url
  }
}
