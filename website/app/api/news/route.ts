import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import type { NewsItem, NewsResponse } from '@/lib/types'

export const runtime = 'edge'
export const revalidate = 1800 // Revalidate every 30 minutes

export async function GET(request: Request) {
  try {
    // Get Supabase credentials from environment
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

    if (!supabaseUrl || !supabaseKey) {
      return NextResponse.json(
        {
          news: [],
          error: 'Supabase configuration missing',
        } as NewsResponse,
        { status: 500 }
      )
    }

    // Create Supabase client
    const supabase = createClient(supabaseUrl, supabaseKey)

    // Parse query parameters
    const { searchParams } = new URL(request.url)
    const limit = parseInt(searchParams.get('limit') || '7', 10)
    const days = parseInt(searchParams.get('days') || '14', 10)

    // Calculate cutoff date
    const cutoffDate = new Date()
    cutoffDate.setDate(cutoffDate.getDate() - days)

    // Fetch news from Supabase
    const { data, error } = await supabase
      .from('sauna_news')
      .select('*')
      .gte('scraped_at', cutoffDate.toISOString())
      .order('published_at', { ascending: false, nullsFirst: false })
      .order('scraped_at', { ascending: false })
      .limit(limit)

    if (error) {
      console.error('Supabase error:', error)
      return NextResponse.json(
        {
          news: [],
          error: 'Failed to fetch news',
        } as NewsResponse,
        { status: 500 }
      )
    }

    // Transform data to match NewsItem type
    const news: NewsItem[] = (data || []).map((item) => ({
      id: item.id,
      title: item.title,
      summary: item.summary,
      source_url: item.source_url,
      published_at: item.published_at,
      scraped_at: item.scraped_at,
      news_type: item.news_type,
      venue_name: item.venue_name,
      is_featured: item.is_featured,
      created_at: item.created_at,
      updated_at: item.updated_at,
    }))

    // Return with cache headers
    return NextResponse.json(
      { news } as NewsResponse,
      {
        status: 200,
        headers: {
          'Cache-Control': 'public, s-maxage=1800, stale-while-revalidate=3600',
        },
      }
    )
  } catch (error) {
    console.error('API error:', error)
    return NextResponse.json(
      {
        news: [],
        error: 'Internal server error',
      } as NewsResponse,
      { status: 500 }
    )
  }
}
