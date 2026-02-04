import { NextRequest, NextResponse } from 'next/server'
import { revalidatePath } from 'next/cache'

export const runtime = 'edge'

/**
 * On-demand revalidation endpoint
 * Called by GitHub Actions after news scraping completes
 * 
 * Usage: POST /api/revalidate?secret=YOUR_SECRET
 */
export async function POST(request: NextRequest) {
  try {
    // Check for secret to confirm this is a legitimate request
    const secret = request.nextUrl.searchParams.get('secret')
    
    if (!secret || secret !== process.env.REVALIDATE_SECRET) {
      return NextResponse.json(
        { message: 'Invalid secret' },
        { status: 401 }
      )
    }

    // Revalidate the news API route
    revalidatePath('/api/news')
    
    // Also revalidate the main page which uses the news data
    revalidatePath('/')

    return NextResponse.json(
      { 
        revalidated: true,
        timestamp: new Date().toISOString()
      },
      { status: 200 }
    )
  } catch (error) {
    console.error('Revalidation error:', error)
    return NextResponse.json(
      { message: 'Error revalidating', error: String(error) },
      { status: 500 }
    )
  }
}
