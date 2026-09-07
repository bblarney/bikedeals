import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App.jsx'

// Build-time render used by scripts/prerender.js. Nothing here ever runs in the
// browser; main.jsx remains the only client entry.
//
// Nothing is fetched here: React Query only fetches from an effect, which
// renderToString never runs. What a page has is what it was handed in `seed`,
// a list of { queryKey, data } that prerender.js fetched beforehand and that
// lib/prerenderData.js keyed to match the hooks. With an empty seed (the API
// was down, or unset for a local build) pages render their empty-data shape:
// headings, copy, nav, footer. That is the fallback, and it is also why the
// API being asleep can never fail a build.
//
// MemoryRouter rather than StaticRouter: a single non-hydrating pass renders
// identically under both, and MemoryRouter is exported from the same entry the
// rest of the app already imports.
export function render(url, seed = []) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  for (const { queryKey, data } of seed) queryClient.setQueryData(queryKey, data)

  // No StrictMode: it double-renders, which is a client-side debugging aid and
  // pure waste in a one-shot string render.
  const html = renderToString(
    <MemoryRouter initialEntries={[url]}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </MemoryRouter>,
  )

  // Dispose the cache before returning. Every query created during the render
  // schedules a garbage-collection timer when it goes inactive - useStats sets
  // gcTime to 10 minutes - and in Node those timers keep the event loop alive
  // long after the HTML is written. That is why `npm run build` sat for exactly
  // ten minutes after "Prerendered 12 routes" before exiting. The client is
  // one-shot and nothing reads from it again, so clearing it is free.
  queryClient.clear()

  return html
}

// Re-exported so prerender.js, which runs in bare node against the built
// bundle, reads the route-to-query map and the URL serialiser from the same
// code the hooks use rather than a copy.
export { prerenderQueries } from './lib/prerenderData.js'
export { queryString } from './lib/queries.js'
