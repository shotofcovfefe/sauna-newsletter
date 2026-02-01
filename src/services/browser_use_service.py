"""Browser Use integration for event scraping via agentic browser automation."""

import os
from typing import List, Optional, Dict, Any
from browser_use_sdk import BrowserUse
from ..models.types import Venue


class BrowserUseService:
    """Service for scraping venue events using Browser Use SDK."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Browser Use service.

        Args:
            api_key: Browser Use API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv("BROWSER_USE_API_KEY")
        if not self.api_key:
            raise ValueError("BROWSER_USE_API_KEY not found in environment")

        # Initialize Browser Use client
        self.client = BrowserUse(api_key=self.api_key)

    def scrape_venue_events(
        self,
        venue: Venue,
        date_range_description: str = "next 7-14 days"
    ) -> Dict[str, Any]:
        """
        Scrape events from a venue's website using Browser Use SDK.

        Args:
            venue: Venue object with name and URL
            date_range_description: Human-readable date range (e.g., "next week")

        Returns:
            Dict with extracted events and metadata
        """
        # Build the task prompt
        task_description = f"""Navigate to {venue.url} and find their events or bookings page.

Extract all upcoming events/sessions in the {date_range_description}.

For each event, extract:
- Event name/title
- Date and time
- Price (if shown)
- Booking/ticket URL
- Brief description (if available)

Focus on:
- Special events (aufguss, sound baths, yoga, socials)
- Ticketed sessions
- Workshops or classes

Ignore:
- General opening hours
- Routine daily sessions (unless they're special/ticketed)

Return results as a structured list with event name, date, time, price, and URL for each event.

Venue: {venue.name}
"""

        try:
            # Create Browser Use task
            task = self.client.tasks.create_task(
                task=task_description,
                llm="browser-use-llm"  # Uses Browser Use's default LLM
            )

            # Execute the task (blocking)
            result = task.complete()

            return {
                "venue_name": venue.name,
                "venue_url": venue.url,
                "success": True,
                "events": result.output,  # Browser Use returns structured output
                "error": None
            }

        except Exception as e:
            print(f"Error scraping {venue.name}: {e}")
            return {
                "venue_name": venue.name,
                "venue_url": venue.url,
                "success": False,
                "events": [],
                "error": str(e)
            }

    def scrape_multiple_venues(
        self,
        venues: List[Venue],
        date_range_description: str = "next 7-14 days"
    ) -> List[Dict[str, Any]]:
        """
        Scrape events from multiple venues sequentially.

        Args:
            venues: List of Venue objects
            date_range_description: Human-readable date range

        Returns:
            List of results (one per venue)
        """
        results = []

        # Execute sequentially (Browser Use SDK handles tasks synchronously)
        for i, venue in enumerate(venues, 1):
            print(f"  [{i}/{len(venues)}] Scraping {venue.name}...")
            result = self.scrape_venue_events(venue, date_range_description)
            print(f"      → {'Success' if result['success'] else 'Failed'}")
            results.append(result)

        return results
