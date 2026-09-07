import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.jsx'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

// Drop the head tags baked in by scripts/prerender.js and by the edge renderer
// at functions/bikes/[id].js. Every route's component declares its own, and
// React appends rather than replacing static tags, so leaving these would give
// the head two conflicting canonicals, two Product nodes, and a stale robots
// directive after the first client-side navigation.
//
// Everything removed here must be re-declared by the mounting component, or it
// is simply lost once JS runs. BikeDetailPage re-declares all three.
document
  .querySelectorAll('[data-prerendered]')
  .forEach((el) => el.remove())

// Start the cache from the data the page was prerendered with, when there is
// any. createRoot throws the prerendered markup away and re-renders, so
// without this the first client render would swap the shop's numbers for a
// dash and the deal cards for a skeleton until the API answered: content, then
// a placeholder, then the same content. Seeding keeps the content on screen.
//
// `updatedAt` is the build time, not now, so every seeded query is already
// stale and refetches on mount: the visitor sees the build's numbers for the
// round trip it takes to fetch today's, never for longer.
const seed = document.getElementById('prerender-state')
if (seed) {
  try {
    const { at, queries } = JSON.parse(seed.textContent)
    const updatedAt = Date.parse(at) || 0
    for (const { queryKey, data } of queries) {
      queryClient.setQueryData(queryKey, data, { updatedAt })
    }
  } catch {
    /* A malformed seed costs one fetch, nothing more. */
  }
  seed.remove()
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
