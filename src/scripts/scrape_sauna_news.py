#!/usr/bin/env python3
"""
Scrape sauna news using Perplexity API.

Usage:
    python src/scripts/scrape_sauna_news.py
    python src/scripts/scrape_sauna_news.py --out data/scraped/my_news.json
    python src/scripts/scrape_sauna_news.py --recency week
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class NewsQuery:
    """A news search query."""
    def __init__(self, query: str, theme: str, context: str):
        self.query = query
        self.theme = theme
        self.context = context


class NewsResult:
    """Result from a Perplexity news search."""
    def __init__(self, query: str, theme: str, answer: str, sources: List[str]):
        self.query = query
        self.theme = theme
        self.answer = answer
        self.sources = sources

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "theme": self.theme,
            "answer": self.answer,
            "sources": self.sources
        }


def create_news_queries() -> List[NewsQuery]:
    """
    Create news search queries based on current implementation.
    Replicates the logic from src/agents/search_agent.py:plan_search_queries
    """
    queries = []

    # NEWS THEMES - looking for recently published announcements/news
    news_themes = [
        ("openings", "new sauna opening announced London",
         "Looking for recently published news about openings in London"),
        ("coming_soon", "sauna coming soon announced London",
         "Looking for recently published news about coming soon in London"),
        ("new_location", "sauna expansion new location London",
         "Looking for recently published news about new location in London"),
        ("closures", "sauna closed closing London",
         "Looking for recently published news about closures in London"),
        ("refurb", "sauna renovation refurbishment London",
         "Looking for recently published news about refurb in London"),
        ("general_news", "sauna news announcement London",
         "Looking for recently published news about london sauna news in London"),
        ("pop-up", "pop-up sauna temporary sauna London",
         "Looking for recently published news about pop-up in London"),
    ]

    for theme, query_text, context in news_themes:
        queries.append(NewsQuery(query_text, theme, context))

    # Broader searches for trends/research/culture
    queries.append(NewsQuery(
        "sauna health benefits research study",
        "general_news",
        "Looking for recent scientific research on sauna health benefits"
    ))

    queries.append(NewsQuery(
        "London wellness trends saunas contrast therapy cold plunge",
        "general_news",
        "Looking for recent articles about wellness/sauna trends in London"
    ))

    queries.append(NewsQuery(
        "sauna culture UK trends communal bathing",
        "general_news",
        "Looking for cultural commentary on sauna trends in the UK"
    ))

    return queries


def build_prompt(query: NewsQuery) -> str:
    """
    Build an enhanced prompt for Perplexity.
    Replicates logic from src/services/perplexity_service.py:_build_prompt
    """
    prompt_parts = [query.query]

    # Add context
    if query.context:
        prompt_parts.append(f"\nContext: {query.context}")

    # Add specific instructions
    prompt_parts.append("""
Please provide:
1. A concise answer (2-4 sentences)
2. Explicit source URLs (official websites, ticketing links, or reputable sources)
3. Specific dates if available (event dates, opening dates, etc.)
4. Categorize findings as: EVENT, NEWS, OPENING, CLOSURE, or OTHER

For events, include:
- Event name/type
- Venue name
- Date(s) and time(s)
- Ticket/booking URL if available

For news/openings/closures, include:
- What changed
- Where (venue/location)
- When (date or timeframe)
- Source URL
""")

    return "\n".join(prompt_parts)


def execute_perplexity_search(
    api_key: str,
    query: NewsQuery,
    recency: str = "month"
) -> NewsResult:
    """
    Execute a Perplexity search.
    Replicates logic from src/services/perplexity_service.py:search
    """
    prompt = build_prompt(query)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "You are a precise research assistant focused on London sauna events and news. Provide concise answers with clear source URLs and dates when available."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "return_citations": True,
        "search_recency_filter": recency
    }

    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        error_detail = response.text
        raise Exception(f"Perplexity API error ({response.status_code}): {error_detail}")

    result_data = response.json()

    # Extract answer and sources
    answer = result_data.get("choices", [{}])[0].get("message", {}).get("content", "")
    citations = result_data.get("citations", [])

    return NewsResult(
        query=query.query,
        theme=query.theme,
        answer=answer,
        sources=citations
    )


def scrape_news(api_key: str, recency: str = "month") -> List[NewsResult]:
    """Execute all news searches."""
    queries = create_news_queries()
    results = []

    print(f"Executing {len(queries)} news searches...")
    print()

    for i, query in enumerate(queries):
        try:
            print(f"  [{i+1}/{len(queries)}] {query.query[:60]}...")
            result = execute_perplexity_search(api_key, query, recency)
            results.append(result)
        except Exception as e:
            print(f"  ✗ Error: {e}")
            # Create empty result on error
            results.append(NewsResult(
                query=query.query,
                theme=query.theme,
                answer=f"Error: {str(e)}",
                sources=[]
            ))

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scrape sauna news using Perplexity API"
    )
    parser.add_argument(
        "--out",
        help="Output JSON file path",
        default=None
    )
    parser.add_argument(
        "--recency",
        help="Search recency filter (week or month)",
        choices=["week", "month"],
        default="month"
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Get API key
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("ERROR: PERPLEXITY_API_KEY not found in environment")
        print("Please set it in your .env file")
        sys.exit(1)

    # Determine output path
    if args.out:
        output_path = Path(args.out)
    else:
        # Create data/scraped directory
        output_dir = Path("data/scraped")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"{timestamp}_news.json"

    print("=" * 70)
    print("Scraping sauna news from Perplexity...")
    print("=" * 70)
    print()

    # Execute searches
    results = scrape_news(api_key, args.recency)

    # Count successes
    successful = sum(1 for r in results if not r.answer.startswith("Error:"))

    print()
    print("=" * 70)
    print("SCRAPING SUMMARY")
    print("=" * 70)
    print(f"Scraped at: {datetime.now().isoformat()}")
    print(f"Recency filter: {args.recency}")
    print()
    print(f"Searches: {successful}/{len(results)} successful")
    print()

    # Prepare output
    output_data = {
        "scraped_at": datetime.now().isoformat(),
        "recency_filter": args.recency,
        "total_queries": len(results),
        "successful_queries": successful,
        "results": [r.to_dict() for r in results]
    }

    # Write output
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"Output written to: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
