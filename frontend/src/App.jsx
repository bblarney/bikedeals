import { Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import Footer from './components/Footer'
import BackToTop from './components/BackToTop'
import FilterSidebar from './components/FilterSidebar'
import BikeGrid from './components/BikeGrid'
import { useBikes, useBikeParams } from './hooks/useBikes'
import { useFilters } from './hooks/useFilters'
import AboutPage from './pages/AboutPage'
import ContactPage from './pages/ContactPage'
import SitemapPage from './pages/SitemapPage'
import TermsPage from './pages/TermsPage'
import PrivacyPage from './pages/PrivacyPage'
import LandingPage from './pages/LandingPage'

function MainLayout() {
  const params = useBikeParams()
  const { data: bikesData, isLoading, isFetching, isError } = useBikes(params)
  const { data: filtersData } = useFilters(params)

  const hasRegion = !!localStorage.getItem('bikegrid_region') || params.city.length > 0
  if (!hasRegion) return <LandingPage onUpdate={params.update} />

  return (
    <>
      <title>BikeGrid — Daily Bike Deals from Australian Shops</title>
      <meta name="description" content="Browse hundreds of discounted bikes from local Australian bike shops. Updated daily. Filter by category, size, and brand." />
      <link rel="canonical" href="https://bikegrid.com.au/" />
      <Header
        total={filtersData?.total_bikes}
        lastScrapedAt={filtersData?.last_scraped_at}
        params={params}
        onUpdate={params.update}
      />
      <div className="flex flex-1 min-h-0">
        <FilterSidebar
          filters={filtersData}
          params={params}
          onUpdate={params.update}
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
      <Routes>
        <Route path="/" element={<MainLayout />} />
        <Route path="/about" element={<StaticLayout><AboutPage /></StaticLayout>} />
        <Route path="/contact" element={<StaticLayout><ContactPage /></StaticLayout>} />
        <Route path="/sitemap" element={<StaticLayout><SitemapPage /></StaticLayout>} />
        <Route path="/terms" element={<StaticLayout><TermsPage /></StaticLayout>} />
        <Route path="/privacy" element={<StaticLayout><PrivacyPage /></StaticLayout>} />
      </Routes>
      <Footer />
      <BackToTop />
    </div>
  )
}
