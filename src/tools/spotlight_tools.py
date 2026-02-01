"""Tools for venue spotlight selection."""

import json
import random
from pathlib import Path
from typing import List, Optional
from ..models.types import Venue, SearchQuery, SearchTheme, PerplexityResult, Candidate


def get_previous_spotlights() -> List[str]:
    """
    Get list of venues that have been spotlighted in previous runs.

    Reads all saved candidate JSON files and extracts spotlight_venue.

    Returns:
        List of venue names that have been spotlighted
    """
    runs_dir = Path("data/runs")
    if not runs_dir.exists():
        return []

    spotlighted = []
    for json_file in runs_dir.glob("*_candidates.json"):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                spotlight = data.get("spotlight_venue")
                if spotlight:
                    spotlighted.append(spotlight)
        except Exception as e:
            print(f"Warning: Could not read {json_file}: {e}")
            continue

    return spotlighted


def select_spotlight_venue(watchlist_venues: List[Venue]) -> Optional[Venue]:
    """
    Select a random watchlist venue that hasn't been spotlighted yet.

    Args:
        watchlist_venues: List of all venues from CSV

    Returns:
        Selected venue or None if all have been spotlighted
    """
    # Get previously spotlighted venues
    previous_spotlights = get_previous_spotlights()

    # Filter to watchlist venues that haven't been spotlighted
    eligible = [
        v for v in watchlist_venues
        if v.watchlist_ind and v.name not in previous_spotlights
    ]

    if not eligible:
        print("⚠ All watchlist venues have been spotlighted! Resetting...")
        # Reset: all watchlist venues are eligible again
        eligible = [v for v in watchlist_venues if v.watchlist_ind]

    # Random selection
    selected = random.choice(eligible)
    print(f"✓ Selected spotlight venue: {selected.name}")
    print(f"  Previously spotlighted: {len(previous_spotlights)} venues")

    return selected


def generate_spotlight_queries(venue: Venue) -> List[str]:
    """
    Generate Perplexity search queries for venue spotlight research.

    Args:
        venue: The venue to research

    Returns:
        List of search query strings
    """
    queries = [
        f"{venue.name} London sauna information",
        f"{venue.name} London reviews",
        f"{venue.name} London pricing",
        f"{venue.name} London events",
        f"{venue.name} London location address",
    ]

    return queries


def research_spotlight_venue(venue: Venue) -> List[PerplexityResult]:
    """
    Research a venue using Perplexity searches.

    Args:
        venue: The venue to research

    Returns:
        List of PerplexityResult objects with venue information
    """
    from ..services.perplexity_service import PerplexityService

    print()
    print(f"Researching spotlight venue: {venue.name}...")
    print("-" * 70)

    perplexity = PerplexityService()

    # Generate search queries
    query_strings = generate_spotlight_queries(venue)
    queries = [SearchQuery(query=q, theme=SearchTheme.GENERAL_NEWS) for q in query_strings]

    # Execute searches
    results = []
    for i, query in enumerate(queries):
        try:
            print(f"  [{i+1}/{len(queries)}] {query.query[:60]}...")
            result = perplexity.search(query)
            results.append(result)
        except Exception as e:
            print(f"  Error searching '{query.query}': {e}")
            # Add empty result on error
            results.append(
                PerplexityResult(
                    query=query.query,
                    answer=f"Error: {str(e)}",
                    sources=[]
                )
            )

    print(f"✓ Completed {len(results)} searches for {venue.name}")

    return results


def format_spotlight_context(
    venue: Venue,
    research_results: List[PerplexityResult],
    scraped_events: List[Candidate]
) -> str:
    """
    Format venue research into context for drafting.

    Args:
        venue: The venue
        research_results: Perplexity search results
        scraped_events: Scraped events to find this venue's events

    Returns:
        Formatted context string for the drafting prompt
    """
    # Find events for this venue
    venue_events = [
        c for c in scraped_events
        if c.source_type == "scrape" and c.venue_match == venue.name
    ]

    # Format research findings
    research_text = "\n\n".join([
        f"**Query**: {r.query}\n**Answer**: {r.answer}\n**Sources**: {', '.join(r.sources[:3])}"
        for r in research_results
        if r.answer and "Error:" not in r.answer
    ])

    context = f"""## VENUE SPOTLIGHT: {venue.name}

You MUST include a "Venue Spotlight" section featuring {venue.name}.

**Basic Info:**
- Name: {venue.name}
- Address: {venue.address}
- Description: {venue.description}
- URL: {venue.url}
- Tags: {', '.join(venue.tags)}

**Events This Week:**
{chr(10).join([f"- {e.title} ({e.date}): {e.summary[:100]}..." for e in venue_events]) if venue_events else "No specific events scraped this week"}

**Research Findings:**

{research_text}

**Spotlight Writing Requirements:**
- Write 2-4 paragraphs about this venue
- Use research findings to provide specific, factual details
- Include what makes it distinctive (pricing, atmosphere, offerings)
- Mention any events happening this week if available
- Link to venue URL on first mention: [{venue.name}]({venue.url})
- Tone: Sharp, observational, opinionated (is it good? for whom? what's the trade-off?)
- Cite sources naturally (e.g., "sessions start at £X according to their latest pricing")
"""

    return context
