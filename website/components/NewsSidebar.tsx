'use client'

import { useEffect, useState } from 'react'
import type { NewsItem } from '@/lib/types'

interface NewsSidebarProps {
  className?: string
}

function formatRelativeDate(dateString: string | null): string {
  if (!dateString) return 'Recently'

  const date = new Date(dateString)
  const now = new Date()
  const diffTime = Math.abs(now.getTime() - date.getTime())
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 14) return '1 week ago'
  return '2 weeks ago'
}

function NewsCard({ news }: { news: NewsItem }) {
  return (
    <div className="group pb-4 border-b border-gray-200 last:border-b-0">
      {/* Date */}
      <span className="text-xs text-gray-400 mb-2 block">
        {formatRelativeDate(news.published_at || news.scraped_at)}
      </span>

      {/* Title */}
      <h3 className="font-semibold text-gray-900 mb-2 leading-snug text-sm">
        {news.title}
      </h3>

      {/* Venue name if available */}
      {news.venue_name && (
        <p className="text-xs text-gray-500 mb-2">{news.venue_name}</p>
      )}

      {/* Summary */}
      <p className="text-sm text-gray-600 line-clamp-2 mb-2">{news.summary}</p>

      {/* Read more link */}
      {news.source_url && (
        <a
          href={news.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-gray-900 hover:underline"
        >
          Read more →
        </a>
      )}
    </div>
  )
}

function NewsCardSkeleton() {
  return (
    <div className="pb-4 border-b border-gray-200 animate-pulse">
      <div className="h-3 w-20 bg-gray-200 rounded mb-2"></div>
      <div className="h-4 w-3/4 bg-gray-300 rounded mb-2"></div>
      <div className="h-3 w-full bg-gray-200 rounded mb-1"></div>
      <div className="h-3 w-5/6 bg-gray-200 rounded mb-2"></div>
      <div className="h-3 w-16 bg-gray-300 rounded"></div>
    </div>
  )
}

export default function NewsSidebar({ className = '' }: NewsSidebarProps) {
  const [news, setNews] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isVisible, setIsVisible] = useState(true)

  useEffect(() => {
    async function fetchNews() {
      try {
        setLoading(true)
        const response = await fetch('/api/news?limit=7')

        if (!response.ok) {
          throw new Error('Failed to fetch news')
        }

        const data = await response.json()
        const items = (data.news || []).slice()
        items.sort((a: NewsItem, b: NewsItem) =>
          new Date(b.published_at || b.scraped_at).getTime() -
          new Date(a.published_at || a.scraped_at).getTime()
        )
        setNews(items)
        setError(data.error || null)
      } catch (err) {
        console.error('Error fetching news:', err)
        setError('Failed to load news')
      } finally {
        setLoading(false)
      }
    }

    fetchNews()

    // Refresh every 30 minutes
    const interval = setInterval(fetchNews, 30 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  if (error && !loading && news.length === 0) {
    return null // Hide sidebar if error and no cached news
  }

  return (
    <>
      {/* Desktop Sidebar - Fixed on LEFT */}
      <div
        className={`hidden lg:block absolute top-0 left-0 w-80 xl:w-96 h-full bg-white border-r border-gray-200 p-6 overflow-y-auto z-20 transition-transform duration-300 ${
          isVisible ? 'translate-x-0' : '-translate-x-full'
        } ${className}`}
        style={{ scrollbarWidth: 'thin' }}
      >
        {/* Header */}
        <div className="mb-6 pb-4 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">
            Sauna News
          </h2>
        </div>

        {/* News items */}
        <div className="space-y-4">
          {loading && news.length === 0 ? (
            <>
              <NewsCardSkeleton />
              <NewsCardSkeleton />
              <NewsCardSkeleton />
            </>
          ) : news.length > 0 ? (
            news.map((item) => <NewsCard key={item.id} news={item} />)
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p className="text-sm">No recent news</p>
            </div>
          )}
        </div>
      </div>

      {/* Toggle Button - Desktop */}
      <button
        onClick={() => setIsVisible(!isVisible)}
        className={`hidden lg:flex absolute top-4 z-20 items-center justify-center w-8 h-8 bg-white border border-gray-200 rounded-r-md shadow-sm hover:bg-gray-50 transition-all duration-300 ${
          isVisible ? 'left-80 xl:left-96' : 'left-0'
        }`}
        aria-label={isVisible ? 'Hide news sidebar' : 'Show news sidebar'}
      >
        <svg
          className={`w-4 h-4 text-gray-600 transition-transform duration-300 ${
            isVisible ? '' : 'rotate-180'
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      {/* Mobile Carousel - Above map */}
      <div className="lg:hidden absolute top-0 left-0 right-0 z-10 bg-white border-b border-gray-200 pb-3">
        <div className="px-4 pt-4">
          {/* Header */}
          <div className="mb-3">
            <h2 className="text-sm font-semibold text-gray-900">
              Sauna News
            </h2>
          </div>

          {/* Horizontal scroll */}
          <div
            className="flex gap-4 overflow-x-auto pb-2 snap-x snap-mandatory"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            {loading && news.length === 0 ? (
              <>
                <div className="flex-none w-72 snap-start">
                  <NewsCardSkeleton />
                </div>
                <div className="flex-none w-72 snap-start">
                  <NewsCardSkeleton />
                </div>
              </>
            ) : news.length > 0 ? (
              news.map((item) => (
                <div key={item.id} className="flex-none w-72 snap-start">
                  <NewsCard news={item} />
                </div>
              ))
            ) : (
              <div className="flex-none w-72 p-4 text-center snap-start">
                <p className="text-sm text-gray-500">No recent news</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add custom scrollbar styles */}
      <style jsx>{`
        div::-webkit-scrollbar {
          width: 6px;
          height: 6px;
        }
        div::-webkit-scrollbar-track {
          background: transparent;
        }
        div::-webkit-scrollbar-thumb {
          background: #cbd5e1;
          border-radius: 3px;
        }
        div::-webkit-scrollbar-thumb:hover {
          background: #94a3b8;
        }
      `}</style>
    </>
  )
}
