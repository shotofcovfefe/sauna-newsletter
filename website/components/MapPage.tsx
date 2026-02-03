'use client'

import { useState, useEffect } from 'react'
import SaunaMap from '@/components/SaunaMap'
import VenueCard from '@/components/VenueCard'
import FilterPanel from '@/components/FilterPanel'
import NewsSidebar from '@/components/NewsSidebar'
import NewsletterSignup from '@/components/NewsletterSignup'
import type { VenueGeoJSON, VenueFeature, FilterOptions } from '@/lib/types'

interface MapPageProps {
  geoJson: VenueGeoJSON
}

export default function MapPage({ geoJson }: MapPageProps) {
  const [selectedVenue, setSelectedVenue] = useState<VenueFeature | null>(null)
  const [filters, setFilters] = useState<FilterOptions>({
    venueTypes: [],
    tags: [],
    saunaTypes: [],
    hasWatchlist: false,
    hasColdImmersion: false,
  })


  const handleVenueSelect = (venue: VenueFeature) => {
    setSelectedVenue(venue)
  }

  const handleCloseCard = () => {
    setSelectedVenue(null)
  }

  const [showNewsletter, setShowNewsletter] = useState(false)

  const handleFilterChange = (newFilters: Partial<FilterOptions>) => {
    setFilters((prev) => ({ ...prev, ...newFilters }))
    // Close venue card when filters change
    setSelectedVenue(null)
  }

  return (
    <main className="min-h-screen bg-gray-50" suppressHydrationWarning>
      {/* Header */}
      <header className="bg-white shadow-md" suppressHydrationWarning>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-extrabold text-primary-600 tracking-tight">
                The London Sauna.
              </h1>
              <p className="text-base text-gray-700 mt-1">
                Discover saunas, steam rooms, and thermal experiences across London
              </p>
            </div>

            {/* Stats */}
            <div className="hidden md:flex items-center gap-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-primary-600">{geoJson.features.length}</p>
              <p className="text-xs text-gray-600">Venues</p>
            </div>
            <div
              className={`text-center cursor-pointer ${
                filters.hasWatchlist ? 'text-primary-700' : ''
              }`}
              onClick={() => {
                const sel = !filters.hasWatchlist
                setFilters({
                  venueTypes: [],
                  tags: [],
                  saunaTypes: [],
                  hasWatchlist: sel,
                  hasColdImmersion: false,
                })
                setSelectedVenue(null)
              }}
            >
              <p className="text-2xl font-bold text-primary-600">
                {geoJson.features.filter((f) => f.properties.isWatchlist).length}
              </p>
              <p className="text-xs text-gray-600">Recommended</p>
            </div>
            <div
              className={`text-center cursor-pointer ${
                filters.hasColdImmersion ? 'text-primary-700' : ''
              }`}
              onClick={() => {
                const sel = !filters.hasColdImmersion
                setFilters({
                  venueTypes: [],
                  tags: [],
                  saunaTypes: [],
                  hasWatchlist: false,
                  hasColdImmersion: sel,
                })
                setSelectedVenue(null)
              }}
            >
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

      </div>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-600">
            Made with heat in London &middot;{' '}
            <a
              href="https://buymeacoffee.com/placeholder"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary-600 hover:text-primary-700 underline"
            >
              support our work
            </a>{' '}
            &middot;{' '}
            <button
              onClick={() => setShowNewsletter(true)}
              className="text-primary-600 hover:text-primary-700 underline"
            >
              newsletter
            </button>
          </p>
        </div>
      </footer>
      <NewsletterSignup
        isOpen={showNewsletter}
        onClose={() => setShowNewsletter(false)}
      />
    </main>
  )
}
