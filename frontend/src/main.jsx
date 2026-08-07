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

// Drop the canonical baked in by scripts/prerender.js. Every route's component
// declares its own, and React appends rather than replacing static tags — so
// leaving this one would leave two conflicting canonicals in the head after the
// first client-side navigation.
document.querySelector('link[rel="canonical"][data-prerendered]')?.remove()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
