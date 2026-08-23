import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App.jsx'

// Build-time render used by scripts/prerender.js. Nothing here ever runs in the
// browser — main.jsx remains the only client entry.
//
// No data is fetched: React Query starts every query in its pending state and
// only fetches from an effect, which renderToString never runs. Pages therefore
// prerender to their empty-data shape (headings, copy, nav, footer) and fill in
// on the client. That is the point — the API can be asleep during a build.
//
// MemoryRouter rather than StaticRouter: a single non-hydrating pass renders
// identically under both, and MemoryRouter is exported from the same entry the
// rest of the app already imports.
export function render(url) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

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
