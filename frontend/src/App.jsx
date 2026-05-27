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

function MainLayout() {
  const params = useBikeParams()
  const { data: bikesData, isLoading, isError } = useBikes(params)
  const { data: filtersData } = useFilters()

  return (
    <>
      <title>BikeDeals — Daily Bike Deals from Australian Shops</title>
      <meta name="description" content="Browse hundreds of discounted bikes from local Australian bike shops. Updated daily. Filter by category, size, and brand." />
      <link rel="canonical" href="https://bikedeals.com.au/" />
      <Header
        total={filtersData?.total_bikes}
        lastScrapedAt={filtersData?.last_scraped_at}
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
      </Routes>
      <Footer />
      <BackToTop />
    </div>
  )
}
