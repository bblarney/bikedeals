import Header from './components/Header'
import FilterStrip from './components/FilterStrip'
import BikeGrid from './components/BikeGrid'
import { useBikes, useBikeParams } from './hooks/useBikes'
import { useFilters } from './hooks/useFilters'

export default function App() {
  const params = useBikeParams()
  const { data: bikesData, isLoading, isError } = useBikes(params)
  const { data: filtersData } = useFilters()

  return (
    <div className="min-h-screen flex flex-col">
      <Header
        total={filtersData?.total_bikes}
        lastScrapedAt={filtersData?.last_scraped_at}
      />
      <FilterStrip
        filters={filtersData}
        params={params}
        onUpdate={params.update}
      />
      <BikeGrid
        bikes={bikesData?.results}
        isLoading={isLoading}
        isError={isError}
        total={bikesData?.total}
        params={params}
        onUpdate={params.update}
      />
    </div>
  )
}
