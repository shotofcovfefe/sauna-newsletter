'use client'

import { useState } from 'react'
import { FunnelIcon, XMarkIcon } from '@heroicons/react/24/outline'
import type { FilterOptions, VenueGeoJSON } from '@/lib/types'

interface FilterPanelProps {
  geoJson: VenueGeoJSON
  onFilterChange: (filters: FilterOptions) => void
}

export default function FilterPanel({ geoJson, onFilterChange }: FilterPanelProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [filters, setFilters] = useState<FilterOptions>({
    venueTypes: [],
    tags: [],
    saunaTypes: [],
    hasWatchlist: false,
    hasColdImmersion: false,
  })

  // Extract unique values from GeoJSON
  const uniqueVenueTypes = Array.from(
    new Set(geoJson.features.map((f) => f.properties.venueType).filter(Boolean))
  ).sort()

  const uniqueTags = Array.from(
    new Set(geoJson.features.flatMap((f) => f.properties.tags))
  ).sort()

  const uniqueSaunaTypes = Array.from(
    new Set(geoJson.features.flatMap((f) => f.properties.saunaTypes))
  ).sort()

  const handleFilterChange = (newFilters: Partial<FilterOptions>) => {
    const updated = { ...filters, ...newFilters }
    setFilters(updated)
    onFilterChange(updated)
  }

  const clearFilters = () => {
    const cleared: FilterOptions = {
      venueTypes: [],
      tags: [],
      saunaTypes: [],
      hasWatchlist: false,
      hasColdImmersion: false,
    }
    setFilters(cleared)
    onFilterChange(cleared)
  }

  const activeFilterCount =
    filters.venueTypes.length +
    filters.tags.length +
    filters.saunaTypes.length +
    (filters.hasWatchlist ? 1 : 0) +
    (filters.hasColdImmersion ? 1 : 0)

  return (
    <>
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed top-4 left-4 z-20 bg-white rounded-lg shadow-lg px-4 py-3 flex items-center gap-2 hover:bg-gray-50 transition-colors"
        suppressHydrationWarning
      >
        <FunnelIcon className="w-5 h-5 text-gray-600" />
        <span className="font-medium text-gray-900">Filters</span>
        {activeFilterCount > 0 && (
          <span className="bg-primary-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
            {activeFilterCount}
          </span>
        )}
      </button>

      {/* Filter Panel */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 z-30"
            onClick={() => setIsOpen(false)}
          />

          {/* Panel */}
          <div className="fixed left-0 top-0 bottom-0 w-80 bg-white shadow-2xl z-40 overflow-y-auto" suppressHydrationWarning>
            {/* Header */}
            <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between" suppressHydrationWarning>
              <h2 className="text-lg font-bold text-gray-900">Filter Venues</h2>
              <button
                onClick={() => setIsOpen(false)}
                className="text-gray-500 hover:text-gray-700 p-1"
                suppressHydrationWarning
              >
                <XMarkIcon className="w-6 h-6" />
              </button>
            </div>

            {/* Filter Content */}
            <div className="p-4 space-y-6">
              {/* Quick Filters */}
              <div>
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Quick Filters</h3>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={filters.hasWatchlist}
                      onChange={(e) => handleFilterChange({ hasWatchlist: e.target.checked })}
                      className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                    />
                    <span className="text-sm text-gray-700">Watchlist only</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={filters.hasColdImmersion}
                      onChange={(e) => handleFilterChange({ hasColdImmersion: e.target.checked })}
                      className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                    />
                    <span className="text-sm text-gray-700">Has cold immersion</span>
                  </label>
                </div>
              </div>

              {/* Venue Types */}
              <div>
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Venue Type</h3>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {uniqueVenueTypes.map((type) => (
                    <label key={type} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={filters.venueTypes.includes(type)}
                        onChange={(e) => {
                          const updated = e.target.checked
                            ? [...filters.venueTypes, type]
                            : filters.venueTypes.filter((t) => t !== type)
                          handleFilterChange({ venueTypes: updated })
                        }}
                        className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                      />
                      <span className="text-sm text-gray-700">{type}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Sauna Types */}
              <div>
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Sauna Type</h3>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {uniqueSaunaTypes.map((type) => (
                    <label key={type} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={filters.saunaTypes.includes(type)}
                        onChange={(e) => {
                          const updated = e.target.checked
                            ? [...filters.saunaTypes, type]
                            : filters.saunaTypes.filter((t) => t !== type)
                          handleFilterChange({ saunaTypes: updated })
                        }}
                        className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                      />
                      <span className="text-sm text-gray-700">{type}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Tags/Vibes */}
              <div>
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Vibe</h3>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {uniqueTags.map((tag) => (
                    <label key={tag} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={filters.tags.includes(tag)}
                        onChange={(e) => {
                          const updated = e.target.checked
                            ? [...filters.tags, tag]
                            : filters.tags.filter((t) => t !== tag)
                          handleFilterChange({ tags: updated })
                        }}
                        className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                      />
                      <span className="text-sm text-gray-700">{tag}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Clear Filters Button */}
              {activeFilterCount > 0 && (
                <button
                  onClick={clearFilters}
                  className="w-full py-2 px-4 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium transition-colors"
                >
                  Clear All Filters
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </>
  )
}
