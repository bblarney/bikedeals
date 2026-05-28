import { useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import Footer from './components/Footer'
import BackToTop from './components/BackToTop'
import FilterSidebar from './components/FilterSidebar'
import BikeGrid from './components/BikeGrid'
import ErrorBoundary from './components/ErrorBoundary'
import { useBikes, useBikeParams } from './hooks/useBikes'
import { useFilters } from './hooks/useFilters'
import { canonicalFor } from './seo'
import AboutPage from './pages/AboutPage'
import ContactPage from './pages/ContactPage'
import SitemapPage from './pages/SitemapPage'
import TermsPage from './pages/TermsPage'
import PrivacyPage from './pages/PrivacyPage'
import LandingPage from './pages/LandingPage'

function MainLayout() {
  const params = useBikeParams()
  const [regionSetThisSession, setRegionSetThisSession] = useState(
    () => !!localStorage.getItem('bikegrid_region')
  )
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const { data: bikesData, isLoading, isFetching, isError } = useBikes(params)
  const { data: filtersData } = useFilters(params)

  const showLanding = !regionSetThisSession && params.city.length === 0
  if (showLanding) {
    return (
      <LandingPage
        onUpdate={(changes) => {
          setRegionSetThisSession(true)
          params.update(changes)
        }}
      />
    )
  }

  function handleChangeRegion() {
    localStorage.removeItem('bikegrid_region')
    params.update({ city: [] })
    // Refresh so the landing page renders cleanly; cheaper than re-architecting state here.
    window.location.assign('/')
  }

  return (
    <>
      <title>BikeGrid — Daily Bike Deals from Australian Shops</title>
      <meta name="description" content="Browse hundreds of discounted bikes from local Australian bike shops. Updated daily. Filter by category, size, and brand." />
      <link rel="canonical" href={canonicalFor('/')} />
      <Header
        total={filtersData?.total_bikes}
        lastScrapedAt={filtersData?.last_scraped_at}
        params={params}
        onUpdate={params.update}
        onChangeRegion={handleChangeRegion}
        onOpenSidebar={() => setSidebarOpen(true)}
      />
      <button
        onClick={() => setSidebarCollapsed(p => !p)}
        aria-label={sidebarCollapsed ? 'Expand filters' : 'Collapse filters'}
        style={{
          left: sidebarCollapsed ? '8px' : '224px',
          transition: 'left 200ms cubic-bezier(0.4, 0, 0.2, 1)',
        }}
        className="hidden md:flex fixed top-1/2 -translate-y-1/2 z-50 w-8 h-8 items-center justify-center bg-white border border-slate-200 rounded-full shadow-md text-slate-500 hover:text-slate-700 hover:bg-slate-50"
      >
        {sidebarCollapsed ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        )}
      </button>
      <div className="flex flex-1 min-h-0">
        <FilterSidebar
          filters={filtersData}
          params={params}
          onUpdate={params.update}
          mobileOpen={sidebarOpen}
          onCloseMobile={() => setSidebarOpen(false)}
          desktopCollapsed={sidebarCollapsed}
        />
        <main className="flex-1 min-w-0 flex flex-col">
          <BikeGrid
            bikes={bikesData?.results}
            isLoading={isLoading}
            isFetching={isFetching}
            isError={isError}
            total={bikesData?.total}
            params={params}
            onUpdate={params.update}
          />
        </main>
      </div>
    </>
  )
}

function StaticLayout({ children }) {
  return (
    <>
      <Header />
      <main className="flex-1 bg-gray-50">{children}</main>
    </>
  )
}

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<MainLayout />} />
          <Route path="/about" element={<StaticLayout><AboutPage /></StaticLayout>} />
          <Route path="/contact" element={<StaticLayout><ContactPage /></StaticLayout>} />
          <Route path="/sitemap" element={<StaticLayout><SitemapPage /></StaticLayout>} />
          <Route path="/terms" element={<StaticLayout><TermsPage /></StaticLayout>} />
          <Route path="/privacy" element={<StaticLayout><PrivacyPage /></StaticLayout>} />
        </Routes>
      </ErrorBoundary>
      <Footer />
      <BackToTop />
    </div>
  )
}
