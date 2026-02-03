'use client'

import type { VenueFeature } from '@/lib/types'
import { XMarkIcon, MapPinIcon, FireIcon } from '@heroicons/react/24/outline'
import { StarIcon } from '@heroicons/react/24/solid'

interface VenueCardProps {
  venue: VenueFeature | null
  onClose: () => void
}

// Helper function to ensure array fields are always arrays
function normalizeArrayField(field: any): string[] {
  if (!field) return []
  if (Array.isArray(field)) return field

  // If it's a string, try to parse as JSON
  if (typeof field === 'string') {
    // Handle empty strings
    if (field.trim() === '') return []

    try {
      const parsed = JSON.parse(field)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      // If JSON parsing fails, check if it looks like a stringified array
      // e.g., "[Finnish]" or "[Finnish, Swedish]"
      const trimmed = field.trim()
      if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        // Remove brackets and split by comma
        const content = trimmed.slice(1, -1).trim()
        if (content === '') return []

        return content.split(',').map(s => s.trim()).filter(Boolean)
      }

      // Single value without brackets
      return [field]
    }
  }

  return []
}

export default function VenueCard({ venue, onClose }: VenueCardProps) {
  if (!venue) return null

  const rawProps = venue.properties

  // Normalize array fields that might be strings from MapLibre
  const props = {
    ...rawProps,
    saunaTypes: normalizeArrayField(rawProps.saunaTypes as any),
    tags: normalizeArrayField(rawProps.tags as any),
  }

  return (
    <div className="absolute top-4 right-4 w-96 bg-white rounded-lg shadow-2xl overflow-hidden z-10 max-h-[calc(100vh-2rem)] flex flex-col" suppressHydrationWarning>
      {/* Header */}
      <div className="bg-gradient-to-r from-primary-600 to-primary-700 text-white p-4 relative" suppressHydrationWarning>
        <button
          onClick={onClose}
          className="absolute top-2 right-2 text-white/80 hover:text-white transition-colors p-1 rounded-full hover:bg-white/10"
          aria-label="Close"
          suppressHydrationWarning
        >
          <XMarkIcon className="w-6 h-6" />
        </button>

        <div className="flex items-start gap-2 pr-8" suppressHydrationWarning>
          {props.isWatchlist && (
            <StarIcon className="w-6 h-6 text-yellow-300 flex-shrink-0 mt-1" title="Watchlist" />
          )}
          <div>
            <h2 className="text-xl font-bold leading-tight">{props.name}</h2>
            <p className="text-primary-100 text-sm mt-1 flex items-start gap-1" suppressHydrationWarning>
              <MapPinIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
              {props.address}
            </p>
          </div>
        </div>
      </div>

      {/* Content - Scrollable */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4" suppressHydrationWarning>
        {/* Description */}
        {props.description && (
          <div>
            <p className="text-gray-700 text-sm leading-relaxed">{props.description}</p>
          </div>
        )}

        {/* Facilities */}
        <div className="grid grid-cols-2 gap-3">
          {props.dryCount > 0 && (
            <div className="bg-primary-50 rounded-lg p-3">
              <p className="text-xs text-primary-700 font-medium">Dry Saunas</p>
              <p className="text-2xl font-bold text-primary-900">{props.dryCount}</p>
            </div>
          )}

          {props.steamCount > 0 && (
            <div className="bg-blue-50 rounded-lg p-3">
              <p className="text-xs text-blue-700 font-medium">Steam Rooms</p>
              <p className="text-2xl font-bold text-blue-900">{props.steamCount}</p>
            </div>
          )}
        </div>

        {/* Sauna Types */}
        {props.saunaTypes.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-1" suppressHydrationWarning>
              <FireIcon className="w-4 h-4" />
              Sauna Types
            </h3>
            <div className="flex flex-wrap gap-2">
              {props.saunaTypes.map((type) => (
                <span
                  key={type}
                  className="px-2 py-1 bg-orange-100 text-orange-800 rounded-full text-xs font-medium"
                >
                  {type}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Tags */}
        {props.tags.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-2">Vibes</h3>
            <div className="flex flex-wrap gap-2">
              {props.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-1 bg-gray-100 text-gray-700 rounded-full text-xs font-medium"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Venue Type */}
        {props.venueType && (
          <div className="pt-2 border-t border-gray-200">
            <p className="text-xs text-gray-600 mb-1">Venue Type</p>
            <p className="text-sm font-medium text-gray-900">{props.venueType}</p>
          </div>
        )}

        {/* Cold Immersion */}
        {props.coldImmersion && (
          <div className="bg-blue-50 rounded-lg p-3">
            <p className="text-xs text-blue-700 font-medium mb-1">Cold Immersion</p>
            <p className="text-sm text-blue-900">{props.coldImmersion}</p>
          </div>
        )}

        {/* Features */}
        <div className="flex flex-wrap gap-3 text-xs">
          {props.hasShowers && (
            <span className="flex items-center gap-1 text-gray-600">
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 12h14M12 5l7 7-7 7"
                />
              </svg>
              Showers Available
            </span>
          )}
        </div>
      </div>

      {/* Footer - Book Button */}
      <div className="border-t border-gray-200 p-4 bg-gray-50">
        <a
          href={props.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full bg-primary-600 hover:bg-primary-700 text-white text-center py-3 rounded-lg font-semibold transition-colors"
        >
          Visit Website
        </a>
      </div>
    </div>
  )
}
