'use client'

import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import type { VenueGeoJSON, VenueFeature, FilterOptions } from '@/lib/types'

interface SaunaMapProps {
  geoJson: VenueGeoJSON
  filters?: FilterOptions
  onVenueSelect?: (venue: VenueFeature) => void
}

// London center coordinates
const LONDON_CENTER: [number, number] = [-0.1276, 51.5074]
const DEFAULT_ZOOM = 11

/**
 * Parse array properties that might be stored as JSON strings by MapLibre
 */
function parseArrayProperty(value: any): string[] {
  if (!value) return []
  if (Array.isArray(value)) return value

  // If it's a string, try to parse as JSON
  if (typeof value === 'string') {
    // Handle empty strings
    if (value.trim() === '') return []

    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      // If JSON parsing fails, check if it looks like a stringified array
      // e.g., "[Finnish]" or "[Finnish, Swedish]"
      const trimmed = value.trim()
      if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        // Remove brackets and split by comma
        const content = trimmed.slice(1, -1).trim()
        if (content === '') return []

        return content.split(',').map((s: string) => s.trim()).filter(Boolean)
      }

      // Single value without brackets
      return [value]
    }
  }

  return []
}

export default function SaunaMap({ geoJson, filters, onVenueSelect }: SaunaMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const [isLoaded, setIsLoaded] = useState(false)

  // Initialize map
  useEffect(() => {
    if (!mapContainer.current || map.current) return

    // Initialize MapLibre
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'carto-light': {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
              'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
              'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
            ],
            tileSize: 256,
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
          },
        },
        layers: [
          {
            id: 'carto-light-layer',
            type: 'raster',
            source: 'carto-light',
            minzoom: 0,
            maxzoom: 22,
          },
        ],
      },
      center: LONDON_CENTER,
      zoom: DEFAULT_ZOOM,
    })

    // Add navigation controls
    map.current.addControl(new maplibregl.NavigationControl(), 'top-right')

    // Wait for map to load
    map.current.on('load', () => {
      setIsLoaded(true)
    })

    // Cleanup
    return () => {
      if (map.current) {
        map.current.remove()
        map.current = null
      }
    }
  }, [])

  // Add GeoJSON data and set up interactions
  useEffect(() => {
    if (!map.current || !isLoaded) return

    const mapInstance = map.current

    // Filter GeoJSON based on filters
    const filteredGeoJson = filters ? filterVenues(geoJson, filters) : geoJson

    // Add or update source
    if (mapInstance.getSource('saunas')) {
      ;(mapInstance.getSource('saunas') as maplibregl.GeoJSONSource).setData(filteredGeoJson)
    } else {
      mapInstance.addSource('saunas', {
        type: 'geojson',
        data: filteredGeoJson,
        cluster: true,
        clusterMaxZoom: 14,
        clusterRadius: 50,
      })

      // Add cluster circle layer
      mapInstance.addLayer({
        id: 'clusters',
        type: 'circle',
        source: 'saunas',
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': ['step', ['get', 'point_count'], '#ef4444', 10, '#dc2626', 30, '#b91c1c'],
          'circle-radius': ['step', ['get', 'point_count'], 20, 10, 30, 30, 40],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#fff',
        },
      })

      // Add cluster count layer
      mapInstance.addLayer({
        id: 'cluster-count',
        type: 'symbol',
        source: 'saunas',
        filter: ['has', 'point_count'],
        layout: {
          'text-field': '{point_count_abbreviated}',
          'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
          'text-size': 12,
        },
        paint: {
          'text-color': '#ffffff',
        },
      })

      // Add individual venue points as simple circles
      mapInstance.addLayer({
        id: 'unclustered-point',
        type: 'circle',
        source: 'saunas',
        filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-color': '#ef4444', // Consistent red for all venues
          'circle-radius': 8,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#fff',
        },
      })

      // Click handlers
      mapInstance.on('click', 'clusters', async (e) => {
        const features = mapInstance.queryRenderedFeatures(e.point, {
          layers: ['clusters'],
        })

        if (!features.length) return

        const clusterId = features[0].properties?.cluster_id
        const source = mapInstance.getSource('saunas') as maplibregl.GeoJSONSource

        try {
          const zoom = await source.getClusterExpansionZoom(clusterId)
          const geometry = features[0].geometry
          if (geometry.type === 'Point') {
            mapInstance.easeTo({
              center: geometry.coordinates as [number, number],
              zoom: zoom || DEFAULT_ZOOM + 2,
            })
          }
        } catch (err) {
          console.error('Error expanding cluster:', err)
        }
      })

      mapInstance.on('click', 'unclustered-point', (e) => {
        if (!e.features || !e.features[0]) return

        const rawFeature = e.features[0]

        // MapLibre serializes array properties as strings, so we need to parse them
        const normalizedFeature: VenueFeature = {
          type: 'Feature',
          geometry: rawFeature.geometry as any,
          properties: {
            ...rawFeature.properties,
            saunaTypes: parseArrayProperty(rawFeature.properties?.saunaTypes),
            tags: parseArrayProperty(rawFeature.properties?.tags),
            dryCount: Number(rawFeature.properties?.dryCount) || 0,
            steamCount: Number(rawFeature.properties?.steamCount) || 0,
            isWatchlist: Boolean(rawFeature.properties?.isWatchlist),
            hasShowers: Boolean(rawFeature.properties?.hasShowers),
          } as any,
        }

        if (onVenueSelect) {
          onVenueSelect(normalizedFeature)
        }

        // Center map on selected venue
        const geometry = rawFeature.geometry
        if (geometry.type === 'Point') {
          mapInstance.flyTo({
            center: geometry.coordinates as [number, number],
            zoom: 15,
          })
        }
      })

      // Change cursor on hover
      mapInstance.on('mouseenter', 'clusters', () => {
        mapInstance.getCanvas().style.cursor = 'pointer'
      })

      mapInstance.on('mouseenter', 'unclustered-point', () => {
        mapInstance.getCanvas().style.cursor = 'pointer'
      })

      mapInstance.on('mouseleave', 'clusters', () => {
        mapInstance.getCanvas().style.cursor = ''
      })

      mapInstance.on('mouseleave', 'unclustered-point', () => {
        mapInstance.getCanvas().style.cursor = ''
      })
    }
  }, [geoJson, filters, isLoaded, onVenueSelect])

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainer} className="absolute inset-0 rounded-lg overflow-hidden shadow-lg" />
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 rounded-lg">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading map...</p>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Filter venues based on filter options
 */
function filterVenues(geoJson: VenueGeoJSON, filters: FilterOptions): VenueGeoJSON {
  const filtered = geoJson.features.filter((feature) => {
    const props = feature.properties

    // Filter by venue type
    if (filters.venueTypes.length > 0 && !filters.venueTypes.includes(props.venueType)) {
      return false
    }

    // Filter by tags
    if (filters.tags.length > 0 && !filters.tags.some((tag) => props.tags.includes(tag))) {
      return false
    }

    // Filter by sauna types
    if (
      filters.saunaTypes.length > 0 &&
      !filters.saunaTypes.some((type) => props.saunaTypes.includes(type))
    ) {
      return false
    }

    // Filter by watchlist
    if (filters.hasWatchlist && !props.isWatchlist) {
      return false
    }

    // Filter by cold immersion
    if (filters.hasColdImmersion && !props.coldImmersion) {
      return false
    }

    return true
  })

  return {
    type: 'FeatureCollection',
    features: filtered,
  }
}
