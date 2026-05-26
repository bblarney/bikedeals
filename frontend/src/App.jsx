import Header from './components/Header'
import FilterSidebar from './components/FilterSidebar'
import BikeGrid from './components/BikeGrid'
import { useBikes, useBikeParams } from './hooks/useBikes'
import { useFilters } from './hooks/useFilters'

export default function App() {
  const params = useBikeParams()
  const { data: bikesData, isLoading, isError } = useBikes(params)
  const { data: filtersData } = useFilters()

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
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
    </div>
  )
}
