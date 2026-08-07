import { useState } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Header from './components/Header'
import Footer from './components/Footer'
import BackToTop from './components/BackToTop'
import ScrollToTop from './components/ScrollToTop'
import FilterSidebar from './components/FilterSidebar'
import BikeGrid from './components/BikeGrid'
import ErrorBoundary from './components/ErrorBoundary'
import { useBikes, useBikeParams } from './hooks/useBikes'
import { usePins } from './hooks/usePins'
import { useFilters } from './hooks/useFilters'
import { useStats } from './hooks/useStats'
import { canonicalFor, buildPageMeta } from './seo'
import { MAIN_SCROLL_ID } from './lib/scroll'
import AboutPage from './pages/AboutPage'
import ContactPage from './pages/ContactPage'
import SitemapPage from './pages/SitemapPage'
import TermsPage from './pages/TermsPage'
import PrivacyPage from './pages/PrivacyPage'
import UnsubscribePage from './pages/UnsubscribePage'
import LandingPage from './pages/LandingPage'
import BikeDetailPage from './pages/BikeDetailPage'
import GuidesHubPage from './pages/guides/GuidesHubPage'
import ElectricBikesPage from './pages/guides/ElectricBikesPage'
import MountainBikesPage from './pages/guides/MountainBikesPage'
import RoadBikesPage from './pages/guides/RoadBikesPage'
import GravelBikesPage from './pages/guides/GravelBikesPage'
import CommuterBikesPage from './pages/guides/CommuterBikesPage'

function MainLayout() {
  const params = useBikeParams()
  // Guarded because this initializer also runs during the build-time prerender,
  // where there is no localStorage. Falling back to false renders the landing
  // page, which is the version we want in the static HTML anyway.
  const [regionSetThisSession, setRegionSetThisSession] = useState(() => {
    try { return !!localStorage.getItem('bikegrid_region') }
    catch { return false }
  })
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const { data: bikesData, isLoading, isFetching, isError } = useBikes(params)
  const { data: filtersData } = useFilters(params)
  const { data: statsData } = useStats()
  const { pinnedBikes, pinnedIds, togglePin, clearPins } = usePins()

  const showLanding = !regionSetThisSession && params.city.length === 0
  if (showLanding) {
    // Declare the same metadata the deal-feed branch does. Without it this
    // branch is the one route React never supplies a canonical for, which
    // leaves the prerendered tag with nothing to replace it (see main.jsx).
    const landingMeta = buildPageMeta(params)
    return (
      <div id={MAIN_SCROLL_ID} className="flex-1 min-h-0 overflow-y-auto flex flex-col">
        <title>{landingMeta.title}</title>
        <meta name="description" content={landingMeta.description} />
        <link rel="canonical" href={landingMeta.canonical} />
        <LandingPage
          onUpdate={(changes) => {
            setRegionSetThisSession(true)
            params.update(changes)
          }}
        />
        <Footer />
      </div>
    )
  }

  function handleChangeRegion() {
    localStorage.removeItem('bikegrid_region')
    params.update({ city: [] })
    // Refresh so the landing page renders cleanly; cheaper than re-architecting state here.
    window.location.assign('/')
  }

  const meta = buildPageMeta(params)
  return (
    <>
      <title>{meta.title}</title>
      <meta name="description" content={meta.description} />
      <link rel="canonical" href={meta.canonical} />
      <Header
        total={filtersData?.total_bikes}
        lastScrapedAt={filtersData?.last_scraped_at}
        params={params}
        onOpenSidebar={() => setSidebarOpen(true)}
      />
      {/* The only scrollable region on the deals page — the header stays put and the
          sidebar sticks beside the grid, but the footer scrolls up past it full-width. */}
      <div id={MAIN_SCROLL_ID} className="flex-1 min-h-0 overflow-y-auto flex flex-col">
        {/* grow/shrink-0 so a short grid still pushes the footer to the bottom, while a
            tall one grows the row instead of being squeezed under the footer. */}
        <div className="flex grow shrink-0">
          <FilterSidebar
            filters={filtersData}
            params={params}
            onUpdate={params.update}
            mobileOpen={sidebarOpen}
            onCloseMobile={() => setSidebarOpen(false)}
            desktopCollapsed={sidebarCollapsed}
          />
          {/* Zero-width rail so the toggle overlays the sidebar's edge without taking
              layout width. Sticky rather than fixed: it shares the sidebar's containing
              block, so at the end of the scroll it rides up with the sidebar's bottom
              edge instead of being left floating over the footer. */}
          <div className="hidden md:block w-0 flex-none">
            <button
              onClick={() => setSidebarCollapsed(p => !p)}
              aria-label={sidebarCollapsed ? 'Expand filters' : 'Collapse filters'}
              style={{
                top: 'calc(50dvh - var(--header-h) / 2 - 16px)',
                marginLeft: sidebarCollapsed ? '8px' : '-16px',
                transition: 'margin-left 200ms cubic-bezier(0.4, 0, 0.2, 1)',
              }}
              className="sticky z-50 flex w-8 h-8 items-center justify-center bg-white border border-slate-200 rounded-full shadow-md text-slate-500 hover:text-slate-700 hover:bg-slate-50"
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
          </div>
          <main className="flex-1 min-w-0 flex flex-col">
            <BikeGrid
              bikes={bikesData?.results}
              isLoading={isLoading}
              isFetching={isFetching}
              isError={isError}
              total={bikesData?.total}
              newToday={statsData?.new_today}
              params={params}
              onUpdate={params.update}
              pinnedBikes={pinnedBikes}
              pinnedIds={pinnedIds}
              onTogglePin={togglePin}
              onClearPins={clearPins}
            />
          </main>
        </div>
        <Footer />
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
  // The deals page is a fixed app shell: the viewport never scrolls, its inner
  // grid column does. Every other route keeps normal document scrolling.
  const isShell = useLocation().pathname === '/'

  return (
    <div className={`flex flex-col bg-gray-50 ${isShell ? 'h-dvh overflow-hidden' : 'min-h-screen'}`}>
      <ScrollToTop />
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<MainLayout />} />
          <Route path="/bikes/:id" element={<StaticLayout><BikeDetailPage /></StaticLayout>} />
          {/* Guides: also listed in src/content/guides.js, which is what
              scripts/prerender.js reads to decide what to prerender. A route
              here without an entry there ships as a 404. */}
          <Route path="/guides" element={<StaticLayout><GuidesHubPage /></StaticLayout>} />
          <Route path="/guides/electric-bikes" element={<StaticLayout><ElectricBikesPage /></StaticLayout>} />
          <Route path="/guides/mountain-bikes" element={<StaticLayout><MountainBikesPage /></StaticLayout>} />
          <Route path="/guides/road-bikes" element={<StaticLayout><RoadBikesPage /></StaticLayout>} />
          <Route path="/guides/gravel-bikes" element={<StaticLayout><GravelBikesPage /></StaticLayout>} />
          <Route path="/guides/commuter-bikes" element={<StaticLayout><CommuterBikesPage /></StaticLayout>} />
          <Route path="/about" element={<StaticLayout><AboutPage /></StaticLayout>} />
          <Route path="/contact" element={<StaticLayout><ContactPage /></StaticLayout>} />
          <Route path="/sitemap" element={<StaticLayout><SitemapPage /></StaticLayout>} />
          <Route path="/terms" element={<StaticLayout><TermsPage /></StaticLayout>} />
          <Route path="/privacy" element={<StaticLayout><PrivacyPage /></StaticLayout>} />
          <Route path="/unsubscribe" element={<StaticLayout><UnsubscribePage /></StaticLayout>} />
        </Routes>
      </ErrorBoundary>
      {/* On the shell route the footer lives inside the scrolling column instead. */}
      {!isShell && <Footer />}
      <BackToTop />
    </div>
  )
}
