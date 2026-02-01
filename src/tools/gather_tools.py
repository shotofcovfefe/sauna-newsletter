"""Tools for gathering newsletter candidates."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


def run_perplexity_searches(search_queries: List[str]) -> Dict[str, Any]:
    """
    Run Perplexity searches for London sauna news and events.

    Args:
        search_queries: List of search queries to execute

    Returns:
        Dictionary with search results and metadata
    """
    from ..services.perplexity_service import PerplexityService
    from ..models.types import SearchQuery

    from ..models.types import SearchTheme

    perplexity = PerplexityService()

    # Convert strings to SearchQuery objects with default theme
    queries = [SearchQuery(query=q, theme=SearchTheme.GENERAL_NEWS) for q in search_queries]

    # Execute searches (parallelized)
    results = perplexity.search_multiple(queries, max_concurrent=5)

    return {
        "num_queries": len(queries),
        "num_results": len(results),
        "results": [
            {
                "query": r.query,
                "answer": r.answer[:500] + "..." if len(r.answer) > 500 else r.answer,
                "sources": r.sources,
                "num_sources": len(r.sources)
            }
            for r in results
        ]
    }


def scrape_all_venues() -> Dict[str, Any]:
    """
    Scrape events from all London sauna venues using the aggregator.

    Returns:
        Dictionary with scraped events and metadata
    """
    from ..scripts.aggregate_sauna_schedules import aggregate_all_scrapers
    from ..utils.event_filters import filter_newsletter_events

    # Run the scraper (scrape 7 days ahead to match newsletter cadence)
    results = aggregate_all_scrapers(days=7)

    # Apply newsletter filtering to exclude high-frequency standard sessions
    filter_result = filter_newsletter_events(results["events"])

    return {
        "num_venues_scraped": results["summary"]["scrapers"]["successful"],
        "total_events": len(filter_result["included"]),
        "total_raw_events": len(results["events"]),
        "events_filtered": len(filter_result["excluded"]),
        "summary": results["summary"],
        "results": filter_result["included"]  # List of filtered event dicts (newsletter-ready)
    }


def deduplicate_candidates(
    perplexity_results: List[Dict],
    scraped_events: List[Dict],
    watchlist_venues: List[str],
    email_candidates: List[Dict] = None
) -> Dict[str, Any]:
    """
    Deduplicate and extract structured candidates from search results.

    Args:
        perplexity_results: Results from Perplexity searches
        scraped_events: Events scraped from venue websites
        watchlist_venues: List of venue names to match against
        email_candidates: Optional list of email-sourced candidates

    Returns:
        Dictionary with deduplicated candidates
    """
    from ..services.gemini_service import GeminiService
    from ..models.types import PerplexityResult, BrowserUseResult, Candidate

    gemini = GeminiService()

    # Convert dicts back to proper types
    perp_results = [
        PerplexityResult(
            query=r["query"],
            answer=r["answer"],
            sources=r.get("sources", [])
        )
        for r in perplexity_results
    ]

    browser_results = [
        BrowserUseResult(
            venue_name=e.get("venue_name", "Unknown"),
            venue_url=e.get("venue_url", ""),
            success=e.get("success", True),
            events=e.get("events", []),
            error=e.get("error")
        )
        for e in scraped_events
    ]

    # Convert email candidates if provided
    email_cands = []
    if email_candidates:
        for ec in email_candidates:
            try:
                email_cands.append(Candidate(**ec))
            except Exception as e:
                print(f"Error converting email candidate: {e}")
                continue

    # Deduplicate using Gemini
    candidates = gemini.deduplicate_and_extract_candidates(
        perplexity_results=perp_results,
        browser_use_results=browser_results,
        email_candidates=email_cands,
        watchlist_names=watchlist_venues,
        previous_issues=[]  # Will be loaded separately
    )

    return {
        "num_candidates": len(candidates),
        "candidates": [
            {
                "type": c.type.value,
                "title": c.title,
                "venue": c.venue_match,
                "date": c.date,
                "summary": c.summary,
                "confidence": c.confidence,
                "urls": c.urls,
                "source_type": c.source_type,
                "email_artifact_id": c.email_artifact_id
            }
            for c in candidates
        ]
    }


def save_candidates(candidates: List[Dict], run_id: str = None) -> Dict[str, Any]:
    """
    Save candidates to disk for future use.

    Args:
        candidates: List of candidate dictionaries
        run_id: Optional run ID (defaults to timestamp)

    Returns:
        Dictionary with save path and metadata
    """
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir = Path("data/runs")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{run_id}_candidates.json"

    data = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "issue_date": datetime.now().isoformat(),
        "num_candidates": len(candidates),
        "candidates": candidates,
        "shortlist": candidates  # Will be filtered later
    }

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    return {
        "run_id": run_id,
        "output_file": str(output_file),
        "num_candidates": len(candidates)
    }


def fetch_email_candidates(min_confidence: float = 0.5, days_back: int = 7) -> Dict[str, Any]:
    """
    Fetch email artifacts from Supabase and convert to candidates.

    This queries the Supabase database for email artifacts that:
    - Are marked as sauna-related
    - Meet the minimum confidence threshold
    - Are from the last N days (default: 7 days to align with newsletter cadence)

    Note: Does NOT filter by usage - allows re-use of email content if still relevant.

    Args:
        min_confidence: Minimum confidence score (0.0-1.0) for sauna-relevance
        days_back: Only include emails from the last N days (default: 7)

    Returns:
        Dictionary with email candidates and metadata
    """
    # Check if Supabase is configured
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        return {
            "num_artifacts": 0,
            "num_candidates": 0,
            "candidates": [],
            "error": "Supabase not configured (missing SUPABASE_URL or SUPABASE_KEY)"
        }

    try:
        from supabase import create_client
        from ..models.types import Candidate, CandidateType
        from datetime import datetime, timedelta, timezone

        # Initialize Supabase client
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

        # Fetch artifacts from last N days (regardless of usage status)
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

        artifacts_response = (
            supabase.table("email_artifacts")
            .select("*, emails!inner(date, sender, subject)")
            .eq("is_sauna_related", True)
            .gte("confidence_score", min_confidence)
            .gte("emails.date", cutoff_date)
            .order("confidence_score", desc=True)
            .execute()
        )

        artifacts = artifacts_response.data or []

        # Convert artifacts to candidates
        candidates = []
        for artifact in artifacts:
            # Infer type from summary (default to "news")
            candidate_type = CandidateType.NEWS
            summary_lower = artifact["summary"].lower()
            if any(word in summary_lower for word in ["event", "session", "class", "workshop"]):
                candidate_type = CandidateType.EVENT
            elif any(word in summary_lower for word in ["opening", "launch", "new"]):
                candidate_type = CandidateType.OPENING
            elif any(word in summary_lower for word in ["closing", "closure", "shut"]):
                candidate_type = CandidateType.CLOSURE

            # Create candidate
            candidate = Candidate(
                type=candidate_type,
                title=artifact["summary"][:100],  # Use first part of summary as title
                venue_match="unknown",  # Will be matched during deduplication
                date=None,  # Email artifacts don't have structured dates
                urls=[],  # Email artifacts don't have URLs
                summary=artifact["compressed_content"],
                confidence=artifact["confidence_score"],
                source_query=None,
                source_type="email",
                email_artifact_id=artifact["id"]
            )
            candidates.append(candidate)

        return {
            "num_artifacts": len(artifacts),
            "num_candidates": len(candidates),
            "candidates": [
                {
                    "type": c.type.value,
                    "title": c.title,
                    "venue_match": c.venue_match,
                    "date": c.date,
                    "summary": c.summary,
                    "confidence": c.confidence,
                    "source_type": c.source_type,
                    "email_artifact_id": c.email_artifact_id,
                    "urls": c.urls
                }
                for c in candidates
            ]
        }

    except Exception as e:
        return {
            "num_artifacts": 0,
            "num_candidates": 0,
            "candidates": [],
            "error": f"Failed to fetch email candidates: {str(e)}"
        }
