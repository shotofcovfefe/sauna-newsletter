"""Gemini Flash integration for deduplication and selection only.

NOTE: Drafting, critique, and revision are now handled by Claude SDK in draft_tools.py
"""

import os
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from ..models.types import PerplexityResult, BrowserUseResult, Candidate, CandidateType


# Pydantic schemas for structured output
class CandidateOutput(BaseModel):
    """Schema for a single candidate extraction."""
    type: str = Field(description="Type: event, news, opening, closure, or other")
    title: str = Field(description="Clear, concise title")
    venue_match: str = Field(description="Venue name from watchlist or 'unknown'")
    date: Optional[str] = Field(description="YYYY-MM-DD or date range or null")
    urls: List[str] = Field(description="List of relevant URLs")
    summary: str = Field(description="2-3 sentence summary")
    confidence: float = Field(description="Confidence score 0.0-1.0")
    source_query: Optional[str] = Field(description="Original search query or venue name")
    source_type: Optional[str] = Field(default="web", description="Source type: web, email, or scrape")
    email_artifact_id: Optional[str] = Field(default=None, description="Email artifact ID if source_type=email")


class CandidatesListOutput(BaseModel):
    """Schema for list of candidates."""
    candidates: List[CandidateOutput] = Field(description="List of extracted candidates")


class ShortlistOutput(BaseModel):
    """Schema for shortlist selection."""
    selected_indices: List[int] = Field(description="Indices of selected candidates (0-based)")


class GeminiService:
    """Service for interacting with Gemini Flash for deduplication and selection tasks only."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini service.

        Args:
            api_key: Gemini API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found")

        # Use Gemini 3 Flash Preview for deduplication and extraction
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=self.api_key,
            temperature=0.1
        )

    def deduplicate_and_extract_candidates(
        self,
        perplexity_results: List[PerplexityResult],
        browser_use_results: List[BrowserUseResult],
        watchlist_names: List[str],
        previous_issues: List[str],
        email_candidates: List[Candidate] = None
    ) -> List[Candidate]:
        """
        Deduplicate search results and extract structured candidates.

        Args:
            perplexity_results: List of Perplexity search results (news)
            browser_use_results: List of Browser Use scraping results (events)
            watchlist_names: List of venue names to match against
            previous_issues: List of previous newsletter markdown content
            email_candidates: Optional list of email-sourced candidates

        Returns:
            List of Candidate objects
        """
        # Build the prompt
        system_prompt = """You are a precise data extraction specialist for a London sauna newsletter.

The newsletter follows this structure:
- Opening think-piece (trends, observations)
- The Moves (venue changes: ↑ expansions, ↓ closures, NEW openings, ⚠ warnings)
- The Rankings (🥇 Best session, 🥈/🥉 runners-up, 🐎 dark horse)
- Weekend Windows (specific time-window recommendations)
- Venue Spotlight (deep dive on one venue - handled separately)
- Optional: One Useful Idea, Sauna Culture Moment

Your task is to analyze FOUR types of inputs:
1. **General News** (Perplexity searches): Industry trends, openings, closures, policy changes
2. **Scraped Events** (from venue websites): Specific sessions, classes, special events
3. **Email Candidates** (from venue newsletters): Promotions, announcements, updates
4. **Spotlight Research** (Perplexity searches about one specific venue - extract separately)

EXTRACTION PRIORITIES (aligned to newsletter template):
- **The Moves**: Openings, closures, expansions, venue changes, policy updates
- **The Rankings**: Notable events worth recommending (special sessions, aufguss, workshops)
- **Weekend Windows**: Time-specific opportunities (Friday evening, Saturday morning, etc.)
- **Think-piece Material**: Trends, pricing patterns, crowd dynamics, cultural observations

DEDUPLICATION RULES:
- Merge items referring to the same event/news (same venue, same date)
- Keep items with different dates separate
- Prefer official URLs (venue pages, ticketing links)
- Email candidates should be matched and merged with web/scrape results

EXTRACTION RULES:
- Each item must have: type, title, venue_match, summary, urls[], confidence (0-1)
- Match venues against the watchlist when possible
- Extract dates in YYYY-MM-DD format
- Confidence reflects information quality
- Scraped events are highly reliable (confidence 0.8-1.0)
- For email candidates: Preserve source_type="email" and email_artifact_id

SPOTLIGHT HANDLING:
- Spotlight queries will be marked with "Researching spotlight venue: {name}"
- Extract these separately - they feed the venue spotlight section
- Focus on: pricing, atmosphere, what makes it distinctive, any events this week

Return a list of candidate objects with:
- type: "event", "news", "opening", "closure", or "other"
- title: Clear, concise title
- venue_match: Venue name from watchlist or "unknown"
- date: YYYY-MM-DD or date range or null
- urls: List of relevant URLs
- summary: 2-3 sentence summary (factual, specific details)
- confidence: Score from 0.0 to 1.0
- source_query: Original search query or venue name"""

        # Compile Perplexity results
        perplexity_text = "\n\n---\n\n".join([
            f"Query: {r.query}\n\nAnswer: {r.answer}\n\nSources: {', '.join(r.sources)}"
            for r in perplexity_results
        ])

        # Compile scraped events with better formatting
        scraped_sections = []
        for r in browser_use_results:
            if r.success and r.events:
                events_list = "\n".join([
                    f"  - {event.get('event_name', 'Unknown')} on {event.get('date', 'TBD')} at {event.get('start_datetime', 'TBD')}"
                    + (f" (URL: {event.get('source_url', 'N/A')})" if event.get('source_url') else "")
                    for event in r.events[:20]  # Limit to 20 events per venue to avoid token explosion
                ])
                scraped_sections.append(
                    f"Venue: {r.venue_name}\nVenue URL: {r.venue_url}\n\nEvents ({len(r.events)} total):\n{events_list}"
                )
            else:
                scraped_sections.append(
                    f"Venue: {r.venue_name}\nVenue URL: {r.venue_url}\nError: {r.error or 'No events found'}"
                )

        scraped_events_text = "\n\n---\n\n".join(scraped_sections)

        # Compile email candidates
        email_candidates = email_candidates or []
        email_text = "\n\n---\n\n".join([
            f"Title: {c.title}\nVenue: {c.venue_match}\nType: {c.type.value}\nConfidence: {c.confidence}\n\nSummary:\n{c.summary}\n\n(source_type: email, artifact_id: {c.email_artifact_id})"
            for c in email_candidates
        ]) if email_candidates else "No email candidates provided."

        # Sample from previous issues (to avoid context explosion)
        prev_issues_sample = "\n\n---\n\n".join(previous_issues[:3]) if previous_issues else "No previous issues available."

        user_prompt = f"""WATCHLIST VENUES:
{', '.join(watchlist_names)}

===== GENERAL NEWS (Perplexity searches) =====
{perplexity_text}

===== SCRAPED EVENTS (from venue websites) =====
{scraped_events_text}

===== EMAIL-SOURCED CANDIDATES =====
{email_text}

===== PREVIOUS ISSUES (for novelty checking) =====
{prev_issues_sample}

Extract all relevant candidates. Remember to align with the newsletter structure: prioritize venue changes for "The Moves", notable events for "The Rankings", and time-specific opportunities for "Weekend Windows"."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        # Use structured output
        llm_with_structure = self.llm.with_structured_output(CandidatesListOutput)

        try:
            response = llm_with_structure.invoke(messages)

            # Convert to Candidate objects
            candidates = []
            for item in response.candidates:
                try:
                    candidate = Candidate(
                        type=CandidateType(item.type if item.type in ["event", "news", "opening", "closure"] else "other"),
                        title=item.title,
                        venue_match=item.venue_match,
                        date=item.date,
                        urls=item.urls,
                        summary=item.summary,
                        confidence=item.confidence,
                        source_query=item.source_query,
                        source_type=item.source_type or "web",
                        email_artifact_id=item.email_artifact_id
                    )
                    candidates.append(candidate)
                except Exception as e:
                    print(f"Error converting candidate: {e}")
                    continue

            return candidates

        except Exception as e:
            print(f"Error calling Gemini for deduplication: {e}")
            return []

    def select_shortlist(
        self,
        candidates: List[Candidate],
        previous_issues: List[str],
        target_count: int = 15
    ) -> List[Candidate]:
        """
        Select a shortlist of candidates for the newsletter.

        Args:
            candidates: List of all candidates
            previous_issues: Previous newsletter content for novelty checking
            target_count: Target number of items in shortlist

        Returns:
            Shortlisted candidates
        """
        system_prompt = f"""You are a newsletter editor selecting the best items for a London sauna newsletter.

SELECTION CRITERIA:
1. Novelty: Has this been covered before? Is there new information?
2. Relevance: Is this useful to London sauna-goers?
3. Timing: Is this happening in the target date range?
4. Quality: High confidence, clear information, good sources
5. Diversity: Mix of events, news, openings (not all the same type)

SELECTION GUIDELINES:
- Aim for ~{target_count} items
- Prioritize high-confidence items (>0.7)
- Include a mix of event types
- Prefer watchlist venues but include interesting new venues
- Avoid repeating items from previous issues unless materially updated

Return a list of selected candidate indices (0-based integers)."""

        # Format candidates
        candidates_text = "\n\n".join([
            f"[{i}] {c.type.value.upper()} | {c.title}\n"
            f"Venue: {c.venue_match} | Date: {c.date or 'TBD'} | Confidence: {c.confidence:.2f}\n"
            f"Summary: {c.summary}\n"
            f"URLs: {', '.join(c.urls)}"
            for i, c in enumerate(candidates)
        ])

        prev_issues_sample = "\n\n---\n\n".join(previous_issues[:2]) if previous_issues else "No previous issues."

        user_prompt = f"""CANDIDATES ({len(candidates)} total):
{candidates_text}

PREVIOUS ISSUES (for novelty checking):
{prev_issues_sample}

Select the best ~{target_count} candidates."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        # Use structured output
        llm_with_structure = self.llm.with_structured_output(ShortlistOutput)

        try:
            response = llm_with_structure.invoke(messages)

            # Return selected candidates
            shortlist = [candidates[i] for i in response.selected_indices if i < len(candidates)]
            return shortlist

        except Exception as e:
            print(f"Error calling Gemini for selection: {e}")
            # Fallback: return top N by confidence
            sorted_candidates = sorted(candidates, key=lambda c: c.confidence, reverse=True)
            return sorted_candidates[:target_count]
