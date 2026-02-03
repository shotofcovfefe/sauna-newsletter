'use client'

import { useState, useEffect } from 'react'
import SaunaMap from '@/components/SaunaMap'
import VenueCard from '@/components/VenueCard'
import FilterPanel from '@/components/FilterPanel'
import NewsletterSignup from '@/components/NewsletterSignup'
import NewsSidebar from '@/components/NewsSidebar'
import type { VenueGeoJSON, VenueFeature, FilterOptions } from '@/lib/types'

interface MapPageProps {
  geoJson: VenueGeoJSON
}

export default function MapPage({ geoJson }: MapPageProps) {
  const [selectedVenue, setSelectedVenue] = useState<VenueFeature | null>(null)
  const [showNewsletter, setShowNewsletter] = useState(false)
  const [filters, setFilters] = useState<FilterOptions>({
    venueTypes: [],
    tags: [],
    saunaTypes: [],
    hasWatchlist: false,
    hasColdImmersion: false,
  })

  // Show newsletter modal after 15 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      setShowNewsletter(true)
    }, 15000)

    return () => clearTimeout(timer)
  }, [])

  const handleVenueSelect = (venue: VenueFeature) => {
    setSelectedVenue(venue)
  }

  const handleCloseCard = () => {
    setSelectedVenue(null)
  }

  const handleFilterChange = (newFilters: FilterOptions) => {
    setFilters(newFilters)
    // Close venue card when filters change
    setSelectedVenue(null)
  }

  return (
    <main className="min-h-screen bg-gray-50" suppressHydrationWarning>
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200" suppressHydrationWarning>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">London Sauna Map</h1>
              <p className="text-sm text-gray-600 mt-1">
                Discover {geoJson.features.length} saunas, steam rooms, and thermal experiences
                across London
              </p>
            </div>

            {/* Stats */}
            <div className="hidden md:flex items-center gap-6">
              <div className="text-center">
                <p className="text-2xl font-bold text-primary-600">{geoJson.features.length}</p>
                <p className="text-xs text-gray-600">Venues</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-primary-600">
                  {geoJson.features.filter((f) => f.properties.isWatchlist).length}
                </p>
                <p className="text-xs text-gray-600">Watchlist</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-primary-600">
                  {geoJson.features.filter((f) => f.properties.coldImmersion).length}
                </p>
                <p className="text-xs text-gray-600">Cold Plunge</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Map Container */}
      <div className="relative h-[calc(100vh-140px)]" suppressHydrationWarning>
        {/* Filter Panel */}
        <FilterPanel geoJson={geoJson} onFilterChange={handleFilterChange} />

        {/* Map */}
        <SaunaMap
          geoJson={geoJson}
          filters={filters}
          onVenueSelect={handleVenueSelect}
        />

        {/* Venue Card */}
        <VenueCard venue={selectedVenue} onClose={handleCloseCard} />

        {/* News Sidebar - Desktop: Left side, Mobile: Top carousel */}
        <NewsSidebar />

        {/* Newsletter Signup Modal - Full screen overlay after 15s */}
        <NewsletterSignup
          isOpen={showNewsletter}
          onClose={() => setShowNewsletter(false)}
        />
      </div>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-600">
            Made with heat in London &middot;{' '}
            <a
              href="https://github.com/yourusername/sauna-map"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary-600 hover:text-primary-700"
            >
              Contribute
            </a>
          </p>
        </div>
      </footer>
    </main>
  )
}
