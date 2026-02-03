# London Sauna Map

An interactive map of saunas, steam rooms, and thermal experiences across London. Built with Next.js, MapLibre GL, and Tailwind CSS.

## Features

- 🗺️ **Interactive Map** - Browse 240+ London sauna venues on an interactive map
- 🔍 **Smart Filters** - Filter by venue type, sauna type, vibes, and amenities
- ⭐ **Watchlist Venues** - Highlighted premium venues
- 🧊 **Cold Immersion** - Filter for venues with ice baths and cold plunges
- 📍 **Detailed Venue Cards** - Click any venue for full details
- 📧 **Newsletter Signup** - Subscribe to weekly sauna updates
- 🎨 **Responsive Design** - Works on desktop, tablet, and mobile

## Tech Stack

- **Framework**: [Next.js 16](https://nextjs.org/) (App Router)
- **Styling**: [Tailwind CSS 3](https://tailwindcss.com/)
- **Maps**: [MapLibre GL JS](https://maplibre.org/)
- **Data**: CSV → GeoJSON at build time
- **Geocoding**: [postcodes.io](https://postcodes.io/) (free, no API key)
- **Icons**: [Heroicons](https://heroicons.com/)
- **Language**: TypeScript

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- The parent project's CSV data at `../data/sauna_list_london_v1.csv`

### Installation

```bash
cd website
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the site.

### Building

The build process includes two steps:

1. **CSV → GeoJSON**: Parses the CSV and geocodes addresses using postcodes.io
2. **Next.js Build**: Creates the optimized production build

```bash
npm run build
```

To run just the geocoding step:

```bash
npm run build:geojson
```

### Production Server

```bash
npm run start
```

## Deployment to Vercel

### Quick Deploy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new)

### Manual Deployment

1. **Install Vercel CLI**:
   ```bash
   npm i -g vercel
   ```

2. **Deploy**:
   ```bash
   vercel
   ```

3. **Production deployment**:
   ```bash
   vercel --prod
   ```

### Environment Variables

No environment variables required! The geocoding uses the free postcodes.io API which doesn't require authentication.

### Build Configuration

The `vercel.json` file is already configured. The build will:
- Run CSV geocoding before the Next.js build
- Generate static GeoJSON at `public/data/saunas.geojson`
- Create an optimized static site

## Project Structure

```
website/
├── app/
│   ├── page.tsx           # Server component (loads data)
│   ├── layout.tsx         # Root layout
│   └── globals.css        # Global styles + Tailwind
├── components/
│   ├── MapPage.tsx        # Client component (main page)
│   ├── SaunaMap.tsx       # MapLibre map component
│   ├── VenueCard.tsx      # Venue detail popup
│   ├── FilterPanel.tsx    # Filter sidebar
│   └── NewsletterSignup.tsx
├── lib/
│   ├── types.ts           # TypeScript types
│   └── csv-to-geojson.ts  # Build-time geocoding
├── scripts/
│   └── build-geojson.ts   # CLI script for geocoding
└── public/
    └── data/
        └── saunas.geojson # Generated at build time
```

## Customization

### Changing Map Style

Edit `components/SaunaMap.tsx` to change the basemap. Current: CARTO Light.

Other free options:
- **OpenStreetMap**: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`
- **CARTO Dark**: `https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png`

### Newsletter Integration

Edit `components/NewsletterSignup.tsx` to connect to your newsletter service:

```typescript
// Example: Mailchimp, ConvertKit, etc.
const response = await fetch('/api/newsletter/subscribe', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email }),
})
```

### Color Theme

Edit `tailwind.config.ts` to change the primary color:

```typescript
primary: {
  // Change these values
  600: '#dc2626',
  700: '#b91c1c',
}
```

## Data Updates

To update venue data:

1. Update `../data/sauna_list_london_v1.csv`
2. Rebuild the GeoJSON:
   ```bash
   npm run build:geojson
   ```
3. Rebuild the site:
   ```bash
   npm run build
   ```

The geocoding will automatically handle new venues.

## Troubleshooting

### Geocoding Failures

If venues fail to geocode:
- Check that addresses include valid UK postcodes
- Verify postcodes at [postcodes.io](https://postcodes.io/)
- Add missing postcodes to the CSV

### Build Errors

If the build fails:
```bash
# Clean and reinstall
rm -rf node_modules .next
npm install
npm run build
```

## Performance

- **Build time**: ~2-3 minutes (geocoding takes ~30s for 240 venues)
- **Page load**: <1s (static generation)
- **Bundle size**: ~300KB (gzipped)
- **Lighthouse score**: 95+ on all metrics

## License

ISC
