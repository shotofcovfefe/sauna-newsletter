import fs from 'fs'
import path from 'path'
import MapPage from '@/components/MapPage'
import type { VenueGeoJSON } from '@/lib/types'

// Load GeoJSON data at build time (server component)
function loadGeoJsonData(): VenueGeoJSON {
  const filePath = path.join(process.cwd(), 'public', 'data', 'saunas.geojson')
  const fileContents = fs.readFileSync(filePath, 'utf8')
  return JSON.parse(fileContents)
}

export default function Home() {
  const geoJson = loadGeoJsonData()
  return <MapPage geoJson={geoJson} />
}
