import { useEffect, useRef, useState } from 'react'
import Header from '../components/Header'
import CategoryBar from '../components/CategoryBar'
import Footer from '../components/Footer'
import FilterSidebar from '../components/FilterSidebar'
import BikeGrid from '../components/BikeGrid'
import { useBikes, useBikeParams } from '../hooks/useBikes'
import { usePins } from '../hooks/usePins'
import { useFilters } from '../hooks/useFilters'
import { useStats } from '../hooks/useStats'
import { useMarket } from '../hooks/useMarket'
import { coverageShares } from '../lib/market'
import { buildPageMeta } from '../seo'
import { MAIN_SCROLL_ID } from '../lib/scroll'
import { REGIONS } from '../constants'
import { ALL_REGIONS, storedRegion } from '../lib/landing'

// Apply the region the visitor picked last time, once, on a URL that does not
// already say which city it wants. This is what is left of the old landing
// gate: the remembering, without the wall.
//
// `replace` so the un-narrowed URL never becomes a back-button destination, and
// a ref rather than state so re-renders cannot re-apply it after the visitor
// has deliberately cleared the city.
function useRememberedRegion(params) {
  const applied = useRef(false)
  useEffect(() => {
    if (applied.current) return
    applied.current = true
    if (params.city.length) return
    const stored = storedRegion()
    if (!stored || stored === ALL_REGIONS) return
    const region = REGIONS.find((r) => r.name === stored)
    if (region?.cities.length) params.update({ city: region.cities }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}

export default function DealsPage({ lockedCategory = null }) {
  const params = useBikeParams(lockedCategory)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const { data: bikesData, isLoading, isFetching, isError } = useBikes(params)
  const { data: filtersData } = useFilters(params)
  const { data: statsData } = useStats()
  // One extra request for two labels, but it is the same hour-cached response
  // /trends and the home page already hold, so in practice it is free.
  const { data: marketData } = useMarket()
  const { pinnedBikes, pinnedIds, togglePin, clearPins } = usePins()

  useRememberedRegion(params)

  const meta = buildPageMeta(params)

  return (
    <>
      <title>{meta.title}</title>
      <meta name="description" content={meta.description} />
      <link rel="canonical" href={meta.canonical} />
      <Header
        params={params}
        onUpdate={params.update}
        onOpenSidebar={() => setSidebarOpen(true)}
        savedCount={pinnedBikes.length}
      />
      <CategoryBar />
      {/* The only scrollable region on the deals page: the header and category
          bar stay put and the sidebar sticks beside the grid, but the footer
          scrolls up past it full-width. */}
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
            coverage={coverageShares(marketData)}
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
                top: 'calc(50dvh - var(--chrome-h) / 2 - 16px)',
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
              shopCount={filtersData?.vendors?.length}
              lastScrapedAt={filtersData?.last_scraped_at}
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
