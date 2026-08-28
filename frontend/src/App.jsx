import { Routes, Route, useLocation } from 'react-router-dom'
import Header from './components/Header'
import Footer from './components/Footer'
import BackToTop from './components/BackToTop'
import ScrollToTop from './components/ScrollToTop'
import ErrorBoundary from './components/ErrorBoundary'
import { CATEGORIES } from './content/categories'
import { isFeedPath } from './lib/routes'
import HomePage from './pages/HomePage'
import DealsPage from './pages/DealsPage'
import AboutPage from './pages/AboutPage'
import ContactPage from './pages/ContactPage'
import DataPage from './pages/DataPage'
import SitemapPage from './pages/SitemapPage'
import TermsPage from './pages/TermsPage'
import PrivacyPage from './pages/PrivacyPage'
import UnsubscribePage from './pages/UnsubscribePage'
import TrendsPage from './pages/TrendsPage'
import BikeDetailPage from './pages/BikeDetailPage'
import GuidesHubPage from './pages/guides/GuidesHubPage'
import ElectricBikesPage from './pages/guides/ElectricBikesPage'
import MountainBikesPage from './pages/guides/MountainBikesPage'
import RoadBikesPage from './pages/guides/RoadBikesPage'
import GravelBikesPage from './pages/guides/GravelBikesPage'
import CommuterBikesPage from './pages/guides/CommuterBikesPage'

function StaticLayout({ children }) {
  return (
    <>
      <Header />
      <main className="flex-1 bg-gray-50">{children}</main>
    </>
  )
}

function HomeLayout({ children }) {
  return (
    <>
      <Header />
      <main className="flex-1 bg-white">{children}</main>
    </>
  )
}

export default function App() {
  // The deal feed is a fixed app shell: the viewport never scrolls, its inner
  // grid column does. Every other route keeps normal document scrolling.
  //
  // isFeedPath, not a bare === : a reload of /deals lands on /deals/ (see
  // lib/routes.js), and treating that as a non-feed route both dropped the
  // shell and rendered the footer a second time, since DealsPage renders its
  // own inside the scrolling column.
  const isShell = isFeedPath(useLocation().pathname)

  return (
    // `relative` is load-bearing, not decoration. Tailwind's `sr-only` is
    // `position: absolute` with no offsets, so without a positioned ancestor its
    // containing block is the initial one: it renders at its static position
    // (which on the feed is thousands of pixels down, inside the scrolling
    // grid), escapes this wrapper's `overflow-hidden`, and extends the
    // *document* to reach it. The result was a fixed-height shell you could
    // still scroll ~4,800px past, into blank white. Positioning the wrapper
    // makes it the containing block, so the clip finally applies to everything
    // it claims to clip. Any visually-hidden text added anywhere below here
    // depends on this.
    <div className={`relative flex flex-col bg-gray-50 ${isShell ? 'h-dvh overflow-hidden' : 'min-h-screen'}`}>
      <ScrollToTop />
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<HomeLayout><HomePage /></HomeLayout>} />
          <Route path="/deals" element={<DealsPage />} />
          {/* Category is a route, not a query parameter: /gravel-bikes is a page
              a crawler can reach and a human can read. content/categories.js is
              also what scripts/prerender.js reads, so a category added there is
              prerendered rather than shipping as a 404. */}
          {CATEGORIES.map((c) => (
            <Route key={c.path} path={c.path} element={<DealsPage lockedCategory={c.category} />} />
          ))}
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
          <Route path="/trends" element={<StaticLayout><TrendsPage /></StaticLayout>} />
          <Route path="/about" element={<StaticLayout><AboutPage /></StaticLayout>} />
          <Route path="/contact" element={<StaticLayout><ContactPage /></StaticLayout>} />
          <Route path="/data" element={<StaticLayout><DataPage /></StaticLayout>} />
          <Route path="/sitemap" element={<StaticLayout><SitemapPage /></StaticLayout>} />
          <Route path="/terms" element={<StaticLayout><TermsPage /></StaticLayout>} />
          <Route path="/privacy" element={<StaticLayout><PrivacyPage /></StaticLayout>} />
          <Route path="/unsubscribe" element={<StaticLayout><UnsubscribePage /></StaticLayout>} />
        </Routes>
      </ErrorBoundary>
      {/* On the feed the footer lives inside the scrolling column instead. */}
      {!isShell && <Footer />}
      <BackToTop />
    </div>
  )
}
