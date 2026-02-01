#!/usr/bin/env python3
"""
Test the reading corner article search independently.

This script runs ONLY the reading corner search node without
running the full gather workflow.

Usage:
    python test_reading_corner_live.py              # Run fresh searches
    python test_reading_corner_live.py --use-cached # Use cached Perplexity results
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.models.types import GraphState, PerplexityResult
from datetime import datetime


def main():
    """Run reading corner search independently."""

    # Parse arguments
    parser = argparse.ArgumentParser(description="Test reading corner article discovery")
    parser.add_argument("--use-cached", action="store_true", help="Use cached Perplexity results instead of running new searches")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    cache_file = Path("data/temp/perplexity_cache.json")

    print("=" * 70)
    print("READING CORNER - STANDALONE TEST")
    print("=" * 70)
    print()

    # Step 1: Get Perplexity results (from cache or fresh)
    if args.use_cached and cache_file.exists():
        print("Loading cached Perplexity results...")
        with open(cache_file, "r") as f:
            cached_data = json.load(f)

        reading_corner_results = [
            PerplexityResult(
                query=r["query"],
                answer=r["answer"],
                sources=r["sources"],
                raw_response=r.get("raw_response", {})  # Optional, defaults to empty dict
            )
            for r in cached_data["results"]
        ]
        print(f"✓ Loaded {len(reading_corner_results)} cached results")
        print()
    else:
        # Check required API keys for Perplexity
        if not os.getenv("PERPLEXITY_API_KEY"):
            print("ERROR: Missing PERPLEXITY_API_KEY")
            sys.exit(1)

        print("Running Perplexity searches...")
        from src.services.perplexity_service import PerplexityService
        from src.models.types import SearchQuery, SearchTheme

        perplexity = PerplexityService()

        search_queries = [
            SearchQuery(
                query="recent sauna health benefits research studies 2026",
                theme=SearchTheme.GENERAL_NEWS,
                context="Looking for recent academic or scientific articles about sauna health benefits"
            ),
            SearchQuery(
                query="sauna culture essays commentary UK London bathing wellness",
                theme=SearchTheme.GENERAL_NEWS,
                context="Looking for cultural or social commentary about sauna culture"
            ),
            SearchQuery(
                query="sauna wellness feature articles London UK bathing",
                theme=SearchTheme.GENERAL_NEWS,
                context="Looking for in-depth feature articles about saunas"
            ),
        ]

        reading_corner_results = perplexity.search_multiple(search_queries, max_concurrent=3)
        print(f"✓ Completed {len(search_queries)} searches")

        # Cache the results (include raw_response for search_results extraction)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results": [
                    {
                        "query": r.query,
                        "answer": r.answer,
                        "sources": r.sources,
                        "raw_response": r.raw_response
                    }
                    for r in reading_corner_results
                ]
            }, f, indent=2)
        print(f"✓ Cached results to: {cache_file}")
        print()

    # Step 2: Run article selection with Gemini
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: Missing GEMINI_API_KEY")
        sys.exit(1)

    print("Analyzing articles with Gemini...")

    from google import genai
    from google.genai import types
    from src.models.types import ReadingCornerArticle
    import time

    start_time = time.time()

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Extract individual articles from search results
    all_articles = []
    for result in reading_corner_results:
        if result.raw_response and "search_results" in result.raw_response:
            for sr in result.raw_response["search_results"]:
                all_articles.append({
                    "title": sr.get("title", ""),
                    "url": sr.get("url", ""),
                    "date": sr.get("date", ""),
                    "snippet": sr.get("snippet", ""),
                    "source": sr.get("source", "web")
                })

    print(f"Extracted {len(all_articles)} articles from search results")

    # Filter out clickbait and low-quality sources
    clickbait_domains = [
        "saunasteamcenter.com",  # Commercial/product sites
        "salussaunas.com",
        "resident.com",
        "hudsonvalleycountry.com",
        "brownhealth.org",
        "cfpic.org",
        "lifestance.com",  # Wellness clinics promoting services
        "aol.com",  # Aggregators
        "happi.com",
        "prnewswire.com",  # Press releases
        "hospitalitynet.org",
        "leisureopportunities.co.uk",
        "spaopportunities.com",
        "professionalbeauty.co.uk",  # Industry trade publications
        "goodspaguide.co.uk",  # Commercial guides
        "elitetraveler.com",  # Luxury lifestyle/marketing
    ]

    def is_quality_source(article):
        """Filter for reputable publications only."""
        url = article["url"].lower()

        # Reject clickbait domains
        for domain in clickbait_domains:
            if domain in url:
                return False

        # Reject articles without dates
        if not article.get("date"):
            return False

        return True

    filtered_articles = [a for a in all_articles if is_quality_source(a)]
    print(f"After filtering: {len(filtered_articles)} quality articles remain")
    print()

    # Check if we have any articles left after filtering
    if len(filtered_articles) == 0:
        print("⚠ No quality articles found after filtering")
        reading_corner_article = None
    else:
        # Build prompt with filtered articles only
        articles_text = ""
        for i, article in enumerate(filtered_articles):
            articles_text += f"\n{i+1}. **{article['title']}**\n"
            articles_text += f"   URL: {article['url']}\n"
            articles_text += f"   Date: {article['date']}\n"
            articles_text += f"   Snippet: {article['snippet']}\n"

        selection_prompt = f"""You are selecting the single most interesting article for the "Reading Corner" section of a London sauna newsletter.

The audience:
- London-based sauna enthusiasts
- Value both scientific rigor and cultural commentary
- Interested in health benefits, community aspects, and sauna culture
- Skeptical of wellness hype, appreciate nuance

Here are {len(filtered_articles)} quality articles from the past 7 days (clickbait and promotional content filtered out):

{articles_text}

Your task:
1. Evaluate each article based on:
   - Recency (published in the last 7 days)
   - Credibility (reputable publication or research)
   - Relevance to the audience
   - Novelty (not basic/generic content)
   - Depth (substantial, not just news brief)

2. Select the SINGLE best article

3. Return ONLY a JSON object in this exact format:
{{
  "title": "Article title",
  "url": "Full article URL",
  "source_publication": "Publication name (e.g., The Guardian, Nature, etc.)",
  "published_date": "Date if available, or null",
  "summary": "2-3 sentences explaining what the article covers and why it's worth reading for this audience",
  "article_type": "research" or "cultural" or "news"
}}

If NO suitable articles are found (e.g., all are too old, too generic, or not credible), return:
{{"no_article_found": true}}

Return only the JSON, no additional text."""

        try:
            print("  Calling Gemini API (gemini-3-flash-preview)...")

            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("Gemini API timed out after 45 seconds")

            # Set 45 second timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(45)

            try:
                response = client.models.generate_content(
                    model='gemini-3-flash-preview',
                    contents=selection_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    )
                )
                signal.alarm(0)  # Cancel timeout
            except TimeoutError:
                signal.alarm(0)
                print("  ✗ gemini-3-flash-preview timed out")
                print("  This model appears to be unreliable. Consider reporting this issue.")
                raise

            response_text = response.text.strip()

            selection_data = json.loads(response_text)

            elapsed_time = time.time() - start_time
            print(f"✓ Analysis complete ({elapsed_time:.1f}s)")

            if selection_data.get("no_article_found"):
                print("⚠ No suitable articles found for Reading Corner")
                reading_corner_article = None
            else:
                reading_corner_article = ReadingCornerArticle(**selection_data)
                print(f"✓ Selected: {reading_corner_article.title}")
                print(f"  Source: {reading_corner_article.source_publication}")
                print(f"  Type: {reading_corner_article.article_type}")

        except Exception as e:
            print(f"⚠ Error: {e}")
            reading_corner_article = None

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()

    # Display search results
    print(f"Perplexity searches completed: {len(reading_corner_results)}")
    print()

    # Display selected article
    if reading_corner_article:
        print("✓ ARTICLE SELECTED:")
        print()
        print(f"Title:       {reading_corner_article.title}")
        print(f"Source:      {reading_corner_article.source_publication}")
        print(f"URL:         {reading_corner_article.url}")
        print(f"Type:        {reading_corner_article.article_type}")
        if reading_corner_article.published_date:
            print(f"Published:   {reading_corner_article.published_date}")
        print()
        print("Summary:")
        print(f"  {reading_corner_article.summary}")
        print()

        # Show how it would appear in newsletter
        print("-" * 70)
        print("NEWSLETTER FORMAT:")
        print("-" * 70)
        print()
        print(f"**{reading_corner_article.title}**")
        print(f"{reading_corner_article.source_publication}")
        print()
        print(reading_corner_article.summary)
        print()
        print(f"[Read the article]({reading_corner_article.url})")
        print()

    else:
        print("⚠ NO ARTICLE SELECTED")
        print()
        print("This could mean:")
        print("  - No articles from the past 7 days were found")
        print("  - Articles found were too generic or low quality")
        print("  - Search queries need adjustment")
        print()

    # Show raw search results for debugging
    print("-" * 70)
    print("RAW SEARCH RESULTS (for debugging):")
    print("-" * 70)

    for i, result in enumerate(reading_corner_results):
        print()
        print(f"Search {i+1}: {result.query}")
        print(f"Answer: {result.answer[:300]}...")
        print(f"Sources ({len(result.sources)}): {', '.join(result.sources[:3])}")

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    sys.exit(0)


if __name__ == "__main__":
    main()
