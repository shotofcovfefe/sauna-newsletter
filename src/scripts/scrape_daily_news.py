#!/usr/bin/env python3
"""
Daily sauna news scraper for the sidebar.

This script:
1. Uses Perplexity to find London sauna news (openings, closures, major news)
2. Uses Gemini to deduplicate and extract structured data
3. Stores results in Supabase

Usage:
    python src/scripts/scrape_daily_news.py
    python src/scripts/scrape_daily_news.py --lookback 14  # For initial seed
    python src/scripts/scrape_daily_news.py --dry-run      # Test without saving
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Add src to path and load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env file from project root
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from src.services.perplexity_service import PerplexityService
from src.services.gemini_service import GeminiService
from src.services.supabase_service import SupabaseService, NewsItem
from src.models.types import SearchQuery, PerplexityResult


class ExtractedNewsItem(BaseModel):
    """Schema for Gemini-extracted news item."""

    title: str = Field(description="Clear, concise headline")
    summary: str = Field(description="1-2 sentence summary")
    source_url: Optional[str] = Field(description="Primary source URL")
    news_type: str = Field(description="Type: opening, closure, major_news, expansion, or other")
    venue_name: Optional[str] = Field(description="Venue name if applicable")
    published_date: Optional[str] = Field(description="Publication date YYYY-MM-DD if available")
    relevance_score: float = Field(description="Relevance score 0.0-1.0")


class NewsExtractionOutput(BaseModel):
    """Schema for list of extracted news items."""

    news_items: List[ExtractedNewsItem] = Field(description="List of extracted news items")


def create_daily_news_queries(recency_filter: str = "day") -> List[SearchQuery]:
    """
    Create focused news queries for daily scraping.

    Args:
        recency_filter: Perplexity recency filter ("day", "week", or "month")

    Returns:
        List of SearchQuery objects
    """
    from src.models.types import SearchTheme

    queries = []

    # Focus on hard news only (no deals, no events)
    # Using "EVENTS" theme as a generic placeholder since these are news queries
    news_themes = [
        (
            "new sauna opening announcement London",
            "Looking for announcements of new sauna venues opening in London in the past 24-48 hours",
        ),
        (
            "sauna closure shutdown London",
            "Looking for news about sauna venues closing or shutting down in London",
        ),
        (
            "sauna expansion new location London",
            "Looking for news about existing sauna brands expanding to new locations in London",
        ),
        (
            "major sauna news London announcement",
            "Looking for significant sauna industry news, policy changes, or major announcements in London",
        ),
        (
            "London wellness sauna industry news",
            "Looking for broader wellness industry news related to saunas in London",
        ),
    ]

    for query_text, context in news_themes:
        queries.append(
            SearchQuery(
                query=query_text,
                theme=SearchTheme.EVENTS,  # Using EVENTS as generic theme for news
                context=context,
            )
        )

    return queries


def deduplicate_with_gemini(
    perplexity_results: List[PerplexityResult],
    existing_hashes: List[str],
    gemini_service: GeminiService,
) -> List[ExtractedNewsItem]:
    """
    Use Gemini to extract and deduplicate news items.

    Args:
        perplexity_results: Raw results from Perplexity
        existing_hashes: List of content hashes already in database
        gemini_service: Gemini service instance

    Returns:
        List of extracted and deduplicated news items
    """
    # Build the prompt
    system_prompt = """You are a news extraction specialist for a London sauna newsletter.

Your task is to:
1. Extract meaningful news items from Perplexity search results
2. Deduplicate similar items (merge if same story, different sources)
3. Filter out: promotional deals, generic events, spam, irrelevant content
4. Focus on: openings, closures, expansions, major industry news, significant announcements

EXTRACTION RULES:
- Each item must have a clear title and concise summary (1-2 sentences)
- Categorize as: opening, closure, major_news, expansion, or other
- Extract venue name if applicable
- Include primary source URL (prefer official sources)
- Extract publication date if available (YYYY-MM-DD format)
- Score relevance: 1.0 = major news, 0.8 = interesting, 0.5 = marginal, <0.5 = skip

DEDUPLICATION:
- If multiple results discuss the same story, merge into one item
- Keep the most detailed/authoritative version
- Combine URLs from multiple sources

OUTPUT:
Return 3-7 high-quality news items. Quality over quantity."""

    # Compile Perplexity results
    perplexity_text = "\n\n===\n\n".join(
        [
            f"Query: {r.query}\n\nAnswer: {r.answer}\n\nSources:\n"
            + "\n".join([f"- {url}" for url in r.sources])
            for r in perplexity_results
        ]
    )

    user_prompt = f"""PERPLEXITY SEARCH RESULTS:
{perplexity_text}

EXISTING NEWS (skip if already covered):
We already have {len(existing_hashes)} news items in the database from the past 14 days.

Extract the best 3-7 news items that are:
1. Truly newsworthy (not just promotional content)
2. Relevant to London sauna enthusiasts
3. Recent and timely
4. Not duplicates of existing coverage"""

    # Use Gemini with structured output
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    llm_with_structure = gemini_service.llm.with_structured_output(NewsExtractionOutput)

    try:
        response = llm_with_structure.invoke(messages)
        # Filter by relevance score
        return [item for item in response.news_items if item.relevance_score >= 0.6]
    except Exception as e:
        print(f"Error calling Gemini for extraction: {e}")
        return []


def convert_to_news_items(extracted_items: List[ExtractedNewsItem]) -> List[NewsItem]:
    """
    Convert Gemini-extracted items to NewsItem objects.

    Args:
        extracted_items: List of ExtractedNewsItem from Gemini

    Returns:
        List of NewsItem objects ready for Supabase
    """
    news_items = []

    for item in extracted_items:
        # Parse date if available
        published_at = None
        if item.published_date:
            try:
                published_at = datetime.fromisoformat(item.published_date)
            except ValueError:
                pass

        # Determine if featured based on relevance score
        is_featured = item.relevance_score >= 0.9

        news_item = NewsItem(
            title=item.title,
            summary=item.summary,
            source_url=item.source_url,
            published_at=published_at,
            news_type=item.news_type,
            venue_name=item.venue_name,
            is_featured=is_featured,
        )
        news_items.append(news_item)

    return news_items


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Scrape daily sauna news for sidebar")
    parser.add_argument(
        "--lookback",
        type=int,
        default=1,
        help="Days to look back (1 for daily, 14 for initial seed)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without saving to database (for testing)",
    )
    parser.add_argument(
        "--limit", type=int, default=5, help="Maximum number of news items to store"
    )

    args = parser.parse_args()

    # Determine recency filter
    if args.lookback <= 1:
        recency_filter = "day"
    elif args.lookback <= 7:
        recency_filter = "week"
    else:
        recency_filter = "month"

    print("=" * 70)
    print("DAILY SAUNA NEWS SCRAPER")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Lookback: {args.lookback} days ({recency_filter} filter)")
    print(f"Dry run: {args.dry_run}")
    print()

    # Initialize services
    try:
        perplexity_service = PerplexityService()
        gemini_service = GeminiService()

        if not args.dry_run:
            supabase_service = SupabaseService()
            print("✓ Services initialized")
        else:
            supabase_service = None
            print("✓ Services initialized (dry run mode)")
    except Exception as e:
        print(f"✗ Error initializing services: {e}")
        sys.exit(1)

    # Step 1: Execute Perplexity searches
    print("\n" + "=" * 70)
    print("STEP 1: PERPLEXITY SEARCH")
    print("=" * 70)

    queries = create_daily_news_queries(recency_filter)
    print(f"Executing {len(queries)} searches...\n")

    # Manually execute searches with custom recency filter
    perplexity_results = []
    for i, query in enumerate(queries):
        try:
            print(f"  [{i+1}/{len(queries)}] {query.query[:60]}...")
            # Note: We'd need to modify PerplexityService to accept recency_filter
            # For now, it's hardcoded to "week" in the service
            result = perplexity_service.search(query)
            perplexity_results.append(result)
        except Exception as e:
            print(f"  ✗ Error: {e}")

    print(f"\n✓ Completed {len(perplexity_results)} searches")

    # Step 2: Get existing hashes for deduplication
    if not args.dry_run:
        existing_hashes = supabase_service.get_recent_hashes(days=14)
        print(f"✓ Found {len(existing_hashes)} existing news items (past 14 days)")
    else:
        existing_hashes = []
        print("✓ Skipping duplicate check (dry run)")

    # Step 3: Extract and deduplicate with Gemini
    print("\n" + "=" * 70)
    print("STEP 2: GEMINI EXTRACTION & DEDUPLICATION")
    print("=" * 70)

    extracted_items = deduplicate_with_gemini(
        perplexity_results, existing_hashes, gemini_service
    )

    print(f"\n✓ Extracted {len(extracted_items)} news items")

    # Step 4: Convert to NewsItem objects
    news_items = convert_to_news_items(extracted_items)

    # Step 5: Filter out duplicates by hash
    if not args.dry_run:
        filtered_items = [
            item for item in news_items if item.content_hash not in existing_hashes
        ]
        print(f"✓ Filtered to {len(filtered_items)} new items (removed duplicates)")
    else:
        filtered_items = news_items

    # Limit to top N by relevance/recency
    top_items = filtered_items[: args.limit]

    # Step 6: Display results
    print("\n" + "=" * 70)
    print(f"EXTRACTED NEWS ITEMS ({len(top_items)})")
    print("=" * 70)

    for i, item in enumerate(top_items):
        print(f"\n[{i+1}] {item.title}")
        print(f"    Type: {item.news_type} | Venue: {item.venue_name or 'N/A'}")
        print(f"    Summary: {item.summary}")
        print(f"    URL: {item.source_url or 'N/A'}")
        print(f"    Featured: {item.is_featured}")

    # Step 7: Save to Supabase
    if not args.dry_run and top_items:
        print("\n" + "=" * 70)
        print("STEP 3: SAVING TO SUPABASE")
        print("=" * 70)

        inserted_count = supabase_service.insert_many_news(top_items)
        print(f"\n✓ Inserted {inserted_count}/{len(top_items)} items")
    else:
        print("\n✓ Skipping save (dry run mode)")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Searches: {len(perplexity_results)}")
    print(f"Extracted: {len(extracted_items)}")
    print(f"New items: {len(filtered_items)}")
    print(f"Saved: {len(top_items) if not args.dry_run else 0}")
    print("=" * 70)


if __name__ == "__main__":
    main()
