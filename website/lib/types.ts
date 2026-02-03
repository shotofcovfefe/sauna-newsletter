export interface VenueData {
  Name: string
  Address: string
  Description: string
  watchlist_ind: string
  n_dry_saunas: string
  n_steam_rooms: string
  sauna_types: string
  tags: string
  venue_primary_function: string
  cold_immersion_setup: string
  showers_available: string
  url: string
}

export interface VenueProperties {
  name: string
  address: string
  description: string
  isWatchlist: boolean
  dryCount: number
  steamCount: number
  saunaTypes: string[]
  tags: string[]
  venueType: string
  coldImmersion: string
  hasShowers: boolean
  url: string
  postcode?: string
}

export interface VenueFeature {
  type: 'Feature'
  geometry: {
    type: 'Point'
    coordinates: [number, number] // [lng, lat]
  }
  properties: VenueProperties
}

export interface VenueGeoJSON {
  type: 'FeatureCollection'
  features: VenueFeature[]
}

export interface FilterOptions {
  venueTypes: string[]
  tags: string[]
  saunaTypes: string[]
  hasWatchlist: boolean
  hasColdImmersion: boolean
}

export type NewsType = 'opening' | 'closure' | 'major_news' | 'expansion' | 'other'

export interface NewsItem {
  id: string
  title: string
  summary: string
  source_url: string | null
  published_at: string | null
  scraped_at: string
  news_type: NewsType
  venue_name: string | null
  is_featured: boolean
  created_at: string
  updated_at: string
}

export interface NewsResponse {
  news: NewsItem[]
  error?: string
}
