import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'London Sauna Map - Find Your Perfect Heat',
  description: 'Discover saunas, steam rooms, and thermal experiences across London. Browse by location, type, and amenities.',
  keywords: ['sauna', 'steam room', 'london', 'wellness', 'spa', 'heat therapy', 'cold plunge'],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} suppressHydrationWarning>
        {children}
      </body>
    </html>
  )
}
