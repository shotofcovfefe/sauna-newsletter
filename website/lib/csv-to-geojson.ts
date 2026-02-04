import Papa from 'papaparse'
import fs from 'fs'
import path from 'path'
import type { VenueData, VenueGeoJSON, VenueFeature, VenueProperties } from './types'

/**
 * Extract UK postcode from address string
 * UK postcodes format: AA9A 9AA, A9A 9AA, A9 9AA, A99 9AA, AA9 9AA, AA99 9AA
 */
function extractPostcode(address: string): string | null {
  const postcodeRegex = /([A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2})/i
  const match = address.match(postcodeRegex)
  return match ? match[1].toUpperCase().replace(/\s+/g, ' ').trim() : null
}

/**
 * Geocode UK postcode using postcodes.io (free, no API key required)
 */
async function geocodePostcode(postcode: string): Promise<[number, number] | null> {
  try {
    const cleanPostcode = postcode.replace(/\s+/g, '')
    const response = await fetch(`https://api.postcodes.io/postcodes/${cleanPostcode}`)

    if (!response.ok) {
      console.warn(`Failed to geocode postcode: ${postcode}`)
      return null
    }

    const data = await response.json()

    if (data.status === 200 && data.result) {
      // Return [lng, lat] for GeoJSON format
      return [data.result.longitude, data.result.latitude]
    }

    return null
  } catch (error) {
    console.error(`Error geocoding postcode ${postcode}:`, error)
    return null
  }
}

/**
 * Parse JSON-like arrays from CSV strings
 * Handles formats like: [Rock, Aromatherapy, Crystal, Salt]
 */
function parseArrayField(field: string): string[] {
  if (!field || field.trim() === '') return []

  try {
    // First try to parse as valid JSON (e.g., ["Rock", "Aromatherapy"])
    const cleaned = field.trim().replace(/^"|"$/g, '')
    return JSON.parse(cleaned)
  } catch {
    // Fallback: handle bracket-delimited arrays without quotes
    // e.g., [Rock, Aromatherapy, Crystal, Salt]
    let processed = field.trim()

    // Remove outer quotes if present
    processed = processed.replace(/^"|"$/g, '')

    // Remove square brackets
    processed = processed.replace(/^\[|\]$/g, '')

    // Split by comma and clean up each item
    return processed
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
  }
}

/**
 * Parse venue data from CSV row
 */
function parseVenueData(row: VenueData): Omit<VenueProperties, 'postcode'> {
  return {
    name: row.Name,
    address: row.Address,
    description: row.Description,
    isWatchlist: row.watchlist_ind === '1',
    dryCount: parseInt(row.n_dry_saunas) || 0,
    steamCount: parseInt(row.n_steam_rooms) || 0,
    saunaTypes: parseArrayField(row.sauna_types),
    tags: parseArrayField(row.tags),
    venueType: row.venue_primary_function,
    coldImmersion: row.cold_immersion_setup,
    hasShowers: row.showers_available === 'TRUE',
    url: row.url,
  }
}

/**
 * Convert CSV to GeoJSON with geocoding
 */
export async function convertCsvToGeoJson(csvPath: string): Promise<VenueGeoJSON> {
  const csvContent = fs.readFileSync(csvPath, 'utf-8')

  return new Promise((resolve, reject) => {
    Papa.parse<VenueData>(csvContent, {
      header: true,
      skipEmptyLines: true,
      complete: async (results) => {
        const features: VenueFeature[] = []
        const geocodingResults: { success: number; failed: number } = { success: 0, failed: 0 }

        console.log(`Processing ${results.data.length} venues...`)

        // Process venues in batches to avoid rate limiting
        const batchSize = 10
        for (let i = 0; i < results.data.length; i += batchSize) {
          const batch = results.data.slice(i, i + batchSize)

          const batchPromises = batch.map(async (row) => {
            const properties = parseVenueData(row)
            const postcode = extractPostcode(row.Address)

            if (!postcode) {
              console.warn(`No postcode found for venue: ${row.Name}`)
              geocodingResults.failed++
              return null
            }

            const coordinates = await geocodePostcode(postcode)

            if (!coordinates) {
              console.warn(`Failed to geocode: ${row.Name} (${postcode})`)
              geocodingResults.failed++
              return null
            }

            geocodingResults.success++

            return {
              type: 'Feature' as const,
              geometry: {
                type: 'Point' as const,
                coordinates,
              },
              properties: {
                ...properties,
                postcode,
              },
            }
          })

          const batchResults = await Promise.all(batchPromises)
          const validFeatures = batchResults.filter((f) => f !== null) as VenueFeature[]
          features.push(...validFeatures)

          // Rate limiting delay between batches
          if (i + batchSize < results.data.length) {
            await new Promise(resolve => setTimeout(resolve, 100))
          }
        }

        console.log(`\nGeocoding complete:`)
        console.log(`✓ Success: ${geocodingResults.success}`)
        console.log(`✗ Failed: ${geocodingResults.failed}`)
        console.log(`Total venues in GeoJSON: ${features.length}`)

        resolve({
          type: 'FeatureCollection',
          features,
        })
      },
      error: (error: Error) => {
        reject(error)
      },
    })
  })
}

/**
 * Build-time script to generate GeoJSON from CSV
 */
export async function buildGeoJson() {
  const csvPath = path.join(process.cwd(), '..', 'data', 'sauna_list_london_v2.csv')
  const outputPath = path.join(process.cwd(), 'public', 'data', 'saunas.geojson')

  console.log('Starting CSV to GeoJSON conversion...')
  console.log(`Reading from: ${csvPath}`)

  const geoJson = await convertCsvToGeoJson(csvPath)

  // Ensure output directory exists
  const outputDir = path.dirname(outputPath)
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true })
  }

  fs.writeFileSync(outputPath, JSON.stringify(geoJson, null, 2))
  console.log(`\nGeoJSON saved to: ${outputPath}`)

  return geoJson
}
