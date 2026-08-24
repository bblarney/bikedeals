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
// React appends rather than replacing static tags — so leaving these would give
// the head two conflicting canonicals, two Product nodes, and a stale robots
// directive after the first client-side navigation.
//
// Everything removed here must be re-declared by the mounting component, or it
// is simply lost once JS runs. BikeDetailPage re-declares all three.
document
  .querySelectorAll('[data-prerendered]')
  .forEach((el) => el.remove())

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
