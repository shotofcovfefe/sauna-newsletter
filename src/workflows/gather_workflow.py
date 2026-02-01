"""Gather workflow: Collect candidates from all sources."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from ..models.types import GraphState


def load_watchlist_node(state: GraphState) -> GraphState:
    """
    Load venue watchlist.

    Args:
        state: Current graph state

    Returns:
        Updated state with watchlist venues
    """
    from ..utils.data_loader import load_watchlist

    print()
    print("[1/5] Loading venue watchlist...")
    print("-" * 70)

    watchlist = load_watchlist()
    state["watchlist_venues"] = watchlist

    print(f"✓ Loaded {len(watchlist)} venues")
    print(f"  - Watchlist venues: {sum(1 for v in watchlist if v.watchlist_ind)}")

    return state


def scrape_venues_node(state: GraphState) -> GraphState:
    """
    Scrape events from all venue websites.

    Args:
        state: Current graph state

    Returns:
        Updated state with scraped events
    """
    from ..tools.gather_tools import scrape_all_venues
    from ..models.types import BrowserUseResult

    print()
    print("[2/5] Scraping venue events...")
    print("-" * 70)

    results = scrape_all_venues()

    # Group events by venue
    from collections import defaultdict
    events_by_venue = defaultdict(list)
    for event in results.get('results', []):
        venue = event.get('venue', 'Unknown')
        events_by_venue[venue].append(event)

    # Convert to BrowserUseResult objects (one per venue)
    browser_results = []
    for venue_name, events in events_by_venue.items():
        # Get venue URL from first event (fallback to empty string)
        venue_url = ''
        if events:
            venue_url = events[0].get('source_url') or events[0].get('booking_url') or ''

        browser_results.append(BrowserUseResult(
            venue_name=venue_name,
            venue_url=venue_url,
            success=True,
            events=events,
            error=None
        ))

    state["browser_use_results"] = browser_results

    print(f"✓ Found {results['total_events']} newsletter-ready events from {results['num_venues_scraped']} venues")
    print(f"  (Filtered out {results.get('events_filtered', 0)} high-frequency standard sessions)")

    return state


def scrape_emails_node(state: GraphState) -> GraphState:
    """
    Scrape new emails from Gmail and process them.

    Args:
        state: Current graph state

    Returns:
        Updated state (unchanged - emails stored in Supabase)
    """
    import os
    from pathlib import Path
    from datetime import datetime, timedelta, timezone
    from supabase import create_client
    from ..services.gmail_service import GmailClient
    from ..services.email_processor_service import EmailProcessorService

    print()
    print("[3/7] Scraping new emails from Gmail...")
    print("-" * 70)

    # Check if required services are configured
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("⚠ Supabase not configured - skipping email scraping")
        return state

    if not os.getenv("GEMINI_API_KEY"):
        print("⚠ Gemini not configured - skipping email scraping")
        return state

    # Check for Gmail token
    token_path = Path("token.json")
    if not token_path.exists():
        print("⚠ Gmail token not found (token.json) - skipping email scraping")
        print("  Run: python src/scripts/generate_gmail_token.py")
        return state

    try:
        # Initialize services
        gmail_client = GmailClient(token_path=str(token_path))
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        processor = EmailProcessorService(
            supabase_client=supabase,
            gemini_api_key=os.getenv("GEMINI_API_KEY")
        )

        # Use incremental fetching: get emails after the latest one in DB
        latest_date = processor.get_latest_email_date()
        if latest_date:
            gmail_query = f"after:{gmail_client.format_date_for_query(latest_date)}"
            print(f"  Fetching emails after: {latest_date}")
        else:
            # No emails in DB: fetch last 7 days (align with newsletter cadence)
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
            timestamp = gmail_client.format_date_for_query(cutoff_date.isoformat())
            gmail_query = f"after:{timestamp}"
            print(f"  No previous emails - fetching last 7 days")

        # Fetch messages
        messages = gmail_client.fetch_messages(query=gmail_query, max_results=100)
        total_fetched = len(messages)

        if total_fetched == 0:
            print("  ✓ No new emails to process")
            return state

        print(f"  Found {total_fetched} new emails")

        # Process emails
        processed_count = 0
        sauna_related_count = 0

        for i, message in enumerate(messages, 1):
            subject = message.get("Subject", "(no subject)")[:50]

            try:
                # Extract body
                raw_body = gmail_client.get_email_body(message)
                if not raw_body:
                    continue

                # Process and store
                result = processor.process_email(message, raw_body)

                if result:
                    processed_count += 1
                    if result["is_sauna_related"]:
                        sauna_related_count += 1

            except Exception as e:
                print(f"  ⚠ Error processing email {i}: {e}")
                continue

        print(f"✓ Processed {processed_count} emails ({sauna_related_count} sauna-related)")

    except Exception as e:
        print(f"⚠ Email scraping failed: {e}")
        # Don't fail the whole workflow - just skip email scraping

    return state


def fetch_emails_node(state: GraphState) -> GraphState:
    """
    Fetch unused email candidates from Supabase (7-day lookback).

    Args:
        state: Current graph state

    Returns:
        Updated state with email candidates
    """
    from ..tools.gather_tools import fetch_email_candidates
    from ..models.types import Candidate

    print()
    print("[4/7] Fetching email candidates from Supabase...")
    print("-" * 70)

    # Fetch with 7-day lookback to align with newsletter cadence
    results = fetch_email_candidates(min_confidence=0.5, days_back=7)

    if results.get("error"):
        print(f"⚠ {results['error']}")
        # Initialize empty list if error
        state["email_candidates"] = []
    else:
        # Convert dicts to Candidate objects
        email_cands = []
        for ec in results.get("candidates", []):
            try:
                email_cands.append(Candidate(**ec))
            except Exception as e:
                print(f"Warning: Failed to parse email candidate: {e}")
                continue

        state["email_candidates"] = email_cands
        print(f"✓ Found {len(email_cands)} unused email candidates")

    return state


def search_news_node(state: GraphState) -> GraphState:
    """
    Search for London sauna news using Perplexity.

    Args:
        state: Current graph state

    Returns:
        Updated state with Perplexity results
    """
    from ..tools.gather_tools import run_perplexity_searches
    from ..models.types import PerplexityResult

    print()
    print("[5/7] Searching for London sauna news...")
    print("-" * 70)

    # Define search queries
    search_queries = [
        "London sauna new openings",
        "London sauna events this week",
        "London sauna closures",
        "London wellness sauna trends",
        "latest scientific studies sauna health benefits",
        "UK sauna culture trends bathing community",
    ]

    results = run_perplexity_searches(search_queries)

    # Convert to PerplexityResult objects
    perp_results = []
    for r in results.get('results', []):
        perp_results.append(PerplexityResult(
            query=r.get('query', ''),
            answer=r.get('answer', ''),
            sources=r.get('sources', [])
        ))

    state["perplexity_results"] = perp_results

    print(f"✓ Completed {results['num_queries']} searches, found {results['num_results']} results")

    return state


def search_reading_corner_node(state: GraphState) -> GraphState:
    """
    Search for interesting sauna articles for Reading Corner.

    Args:
        state: Current graph state

    Returns:
        Updated state with reading corner article
    """
    from ..services.perplexity_service import PerplexityService
    from ..services.gemini_service import GeminiService
    from ..models.types import SearchQuery, SearchTheme, PerplexityResult, ReadingCornerArticle
    import json

    print()
    print("[6/7] Searching for Reading Corner articles...")
    print("-" * 70)

    perplexity = PerplexityService()

    # Define search queries targeting different article types
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

    # Execute searches
    results = perplexity.search_multiple(search_queries, max_concurrent=3)
    state["reading_corner_results"] = results

    print(f"✓ Completed {len(search_queries)} searches")
    print()
    print("Analyzing articles with Gemini...")

    # Use Google GenAI SDK (new package)
    from google import genai
    from google.genai import types
    import os
    import time

    start_time = time.time()

    # Configure Gemini client
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Extract individual articles from search results instead of summaries
    all_articles = []
    for result in results:
        if result.raw_response and "search_results" in result.raw_response:
            for sr in result.raw_response["search_results"]:
                all_articles.append({
                    "title": sr.get("title", ""),
                    "url": sr.get("url", ""),
                    "date": sr.get("date", ""),
                    "snippet": sr.get("snippet", ""),
                })

    print(f"  Extracted {len(all_articles)} articles from search results")

    # Filter out clickbait and low-quality sources
    clickbait_domains = [
        "saunasteamcenter.com",
        "salussaunas.com",
        "resident.com",
        "hudsonvalleycountry.com",
        "brownhealth.org",
        "cfpic.org",
        "lifestance.com",
        "aol.com",
        "happi.com",
        "prnewswire.com",
        "hospitalitynet.org",
        "leisureopportunities.co.uk",
        "spaopportunities.com",
        "professionalbeauty.co.uk",
        "goodspaguide.co.uk",
        "elitetraveler.com",
    ]

    def is_quality_source(article):
        """Filter for reputable publications only."""
        url = article["url"].lower()
        for domain in clickbait_domains:
            if domain in url:
                return False
        if not article.get("date"):
            return False
        return True

    filtered_articles = [a for a in all_articles if is_quality_source(a)]
    print(f"  After filtering: {len(filtered_articles)} quality articles")

    # Check if we have any articles left after filtering
    if len(filtered_articles) == 0:
        print("  ⚠ No quality articles found after filtering")
        state["reading_corner_article"] = None
        return state

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
        # Generate with timeout using new API
        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=selection_prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",  # Force JSON output
            )
        )

        response_text = response.text.strip()
        selection_data = json.loads(response_text)

        elapsed_time = time.time() - start_time
        print(f"✓ Analysis complete ({elapsed_time:.1f}s)")

        if selection_data.get("no_article_found"):
            print("⚠ No suitable articles found for Reading Corner")
            state["reading_corner_article"] = None
        else:
            article = ReadingCornerArticle(**selection_data)
            state["reading_corner_article"] = article
            print(f"✓ Selected: {article.title}")
            print(f"  Source: {article.source_publication}")
            print(f"  Type: {article.article_type}")

    except Exception as e:
        print(f"⚠ Error selecting article: {e}")
        state["reading_corner_article"] = None

    return state


def deduplicate_node(state: GraphState) -> GraphState:
    """
    Deduplicate and extract structured candidates from all sources.

    Args:
        state: Current graph state

    Returns:
        Updated state with candidates
    """
    from ..services.gemini_service import GeminiService
    import json

    print()
    print("[6/7] Deduplicating and extracting candidates...")
    print("-" * 70)

    # Save raw inputs before deduplication for debugging/review
    raw_dir = Path("data/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file = raw_dir / f"{state['run_id']}_raw_inputs.json"

    raw_data = {
        "run_id": state["run_id"],
        "timestamp": datetime.now().isoformat(),
        "perplexity_results": [
            {
                "query": r.query,
                "answer": r.answer,
                "sources": r.sources
            }
            for r in state["perplexity_results"]
        ],
        "scraped_events_by_venue": [
            {
                "venue_name": r.venue_name,
                "venue_url": r.venue_url,
                "num_events": len(r.events) if r.events else 0,
                "events": r.events[:50]  # Limit to first 50 per venue to avoid huge files
            }
            for r in state["browser_use_results"]
        ],
        "email_candidates": [
            {
                "title": c.title,
                "venue_match": c.venue_match,
                "type": c.type.value,
                "summary": c.summary,
                "confidence": c.confidence,
                "email_artifact_id": c.email_artifact_id
            }
            for c in state.get('email_candidates', [])
        ]
    }

    with open(raw_file, "w") as f:
        json.dump(raw_data, f, indent=2)

    print(f"✓ Saved raw inputs to: {raw_file}")

    gemini = GeminiService()

    # Get watchlist names
    watchlist_names = [v.name for v in state["watchlist_venues"]]

    # Get email candidates (may be empty list)
    email_cands = state.get('email_candidates', [])

    # Deduplicate using Gemini
    candidates = gemini.deduplicate_and_extract_candidates(
        perplexity_results=state["perplexity_results"],
        browser_use_results=state["browser_use_results"],
        email_candidates=email_cands,
        watchlist_names=watchlist_names,
        previous_issues=[]  # Not needed during gathering
    )

    state["candidates"] = candidates

    print(f"✓ Extracted {len(candidates)} unique candidates")

    # Print breakdown by source
    web_count = sum(1 for c in candidates if c.source_type == "web")
    scrape_count = sum(1 for c in candidates if c.source_type == "scrape")
    email_count = sum(1 for c in candidates if c.source_type == "email")

    print()
    print("Breakdown by source:")
    print(f"  - Web/news: {web_count}")
    print(f"  - Scraped events: {scrape_count}")
    print(f"  - Emails: {email_count}")

    return state


def spotlight_venue_node(state: GraphState) -> GraphState:
    """
    Select a venue for spotlight and research it via Perplexity.

    Args:
        state: Current graph state

    Returns:
        Updated state with spotlight venue and research results
    """
    from ..tools.spotlight_tools import select_spotlight_venue, research_spotlight_venue

    print()
    print("[7/7] Selecting and researching spotlight venue...")
    print("-" * 70)

    # Select venue
    spotlight_venue = select_spotlight_venue(state["watchlist_venues"])

    if not spotlight_venue:
        print("⚠ No spotlight venue selected")
        state["spotlight_venue"] = None
        return state

    state["spotlight_venue"] = spotlight_venue

    # Research the venue using Perplexity
    spotlight_results = research_spotlight_venue(spotlight_venue)

    # Store spotlight research separately (don't mix with general news)
    state["spotlight_research"] = spotlight_results

    return state


def save_candidates_node(state: GraphState) -> GraphState:
    """
    Save candidates to disk.

    Args:
        state: Current graph state

    Returns:
        Updated state (unchanged)
    """
    import json

    print()
    print("Saving candidates to disk...")
    print("-" * 70)

    # Create output directory
    output_dir = Path("data/runs")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create output file
    output_file = output_dir / f"{state["run_id"]}_candidates.json"

    # Serialize candidates
    data = {
        "run_id": state["run_id"],
        "timestamp": datetime.now().isoformat(),
        "issue_date": state["issue_date"].isoformat() if state["issue_date"] else datetime.now().isoformat(),
        "num_candidates": len(state["candidates"]),
        "candidates": [c.model_dump() for c in state["candidates"]],
        "spotlight_venue": state["spotlight_venue"].name if state["spotlight_venue"] else None,
        "spotlight_research": [
            {
                "query": r.query,
                "answer": r.answer,
                "sources": r.sources
            }
            for r in state.get("spotlight_research", [])
        ] if state.get("spotlight_research") else [],
        "reading_corner_article": state["reading_corner_article"].model_dump() if state.get("reading_corner_article") else None
    }

    # Write to file
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✓ Saved to: {output_file}")

    return state


def create_gather_workflow() -> StateGraph:
    """
    Create the gather workflow.

    Flow:
    load_watchlist → scrape_venues → scrape_emails → fetch_emails → search_news → search_reading_corner → deduplicate → spotlight → save

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("load_watchlist", load_watchlist_node)
    workflow.add_node("scrape_venues", scrape_venues_node)
    workflow.add_node("scrape_emails", scrape_emails_node)
    workflow.add_node("fetch_emails", fetch_emails_node)
    workflow.add_node("search_news", search_news_node)
    workflow.add_node("search_reading_corner", search_reading_corner_node)
    workflow.add_node("deduplicate", deduplicate_node)
    workflow.add_node("spotlight", spotlight_venue_node)
    workflow.add_node("save", save_candidates_node)

    # Define edges (linear workflow)
    workflow.set_entry_point("load_watchlist")
    workflow.add_edge("load_watchlist", "scrape_venues")
    workflow.add_edge("scrape_venues", "scrape_emails")
    workflow.add_edge("scrape_emails", "fetch_emails")
    workflow.add_edge("fetch_emails", "search_news")
    workflow.add_edge("search_news", "search_reading_corner")
    workflow.add_edge("search_reading_corner", "deduplicate")
    workflow.add_edge("deduplicate", "spotlight")
    workflow.add_edge("spotlight", "save")
    workflow.add_edge("save", END)

    return workflow.compile()


def build_gather_state(run_id: str = None) -> GraphState:
    """
    Build initial state for gather workflow.

    Args:
        run_id: Optional run ID (defaults to timestamp)

    Returns:
        Initial GraphState
    """
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    state = GraphState(
        run_id=run_id,
        issue_date=datetime.now(),
        max_iterations=0,  # Not used in gather
        iteration_count=0,
        watchlist_venues=[],
        perplexity_results=[],
        browser_use_results=[],
        candidates=[],
        search_queries=[],
        previous_issues=[],
        draft=None,
        critique=None,
        notion_page_id=None,
        spotlight_venue=None,
        spotlight_research=[],
        previous_spotlights=[],
        reading_corner_results=[],
        reading_corner_article=None,
        email_candidates=[]
    )

    return state


def run_gather_workflow(run_id: str = None) -> Dict[str, Any]:
    """
    Run the gather workflow.

    Args:
        run_id: Optional run ID (defaults to timestamp)

    Returns:
        Final state
    """
    print("=" * 70)
    print("GATHER WORKFLOW - Collect Newsletter Candidates")
    print("=" * 70)

    # Build state
    initial_state = build_gather_state(run_id=run_id)

    # Create and run workflow
    workflow = create_gather_workflow()

    # Execute
    final_state = workflow.invoke(initial_state)

    print()
    print("=" * 70)
    print("GATHER WORKFLOW COMPLETE")
    print("=" * 70)
    print(f"Run ID: {final_state['run_id']}")
    print(f"Total candidates: {len(final_state['candidates'])}")
    print()
    print("Next step:")
    print(f"  python draft.py --run-id {final_state['run_id']}")
    print()

    return final_state
