#!/usr/bin/env tsx

import { buildGeoJson } from '../lib/csv-to-geojson'

async function main() {
  try {
    await buildGeoJson()
    console.log('\n✓ GeoJSON build complete!')
    process.exit(0)
  } catch (error) {
    console.error('\n✗ GeoJSON build failed:', error)
    process.exit(1)
  }
}

main()
