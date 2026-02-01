#!/usr/bin/env python3
"""
Unified data model for scraped sauna events across all venues and booking platforms.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ScrapedEvent(BaseModel):
    """
    Normalized sauna event across all scraping sources.

    This provides a common schema for events from:
    - Arc Community (Marianatek)
    - Community Sauna (LegitFit)
    - Rebase (Mindbody)
    - Sauna & Plunge (Momence)
    - Rooftop Saunas
    """

    # Core identification
    venue: str = Field(..., description="Venue name (e.g., 'Arc Community', 'Rebase')")
    event_name: str = Field(..., description="Event/class name")

    # Temporal data
    start_datetime: Optional[str] = Field(None, description="ISO 8601 datetime or time string")
    end_datetime: Optional[str] = Field(None, description="ISO 8601 datetime or time string")
    date: Optional[str] = Field(None, description="Date string (YYYY-MM-DD) if datetime not available")

    # Location details
    location: Optional[str] = Field(None, description="Specific location/address if multi-venue")

    # Booking details
    price: Optional[str] = Field(None, description="Price information (e.g., '£15', 'Drop-in £20')")
    availability: Optional[str] = Field(None, description="Availability status (e.g., 'Available', 'Sold Out', '5 spots')")
    capacity: Optional[int] = Field(None, description="Total capacity")
    spots_available: Optional[int] = Field(None, description="Number of spots remaining")
    booking_url: Optional[str] = Field(None, description="Direct booking/signup URL")

    # Instructor/host
    instructor: Optional[str] = Field(None, description="Instructor or host name")

    # Metadata
    source: str = Field(..., description="Source scraper identifier (e.g., 'arc_marianatek')")
    source_url: Optional[str] = Field(None, description="Original source URL")
    scraped_at: str = Field(..., description="ISO 8601 timestamp when scraped")

    # Raw data for debugging
    raw: Optional[Dict[str, Any]] = Field(None, description="Original raw data from scraper")

    def dedup_key(self) -> tuple:
        """
        Generate a key for deduplication.
        Events with same venue, date, time, and name are likely duplicates.
        """
        # Normalize time strings for comparison
        time_str = self.start_datetime or self.date or ""
        name_normalized = (self.event_name or "").lower().strip()
        venue_normalized = (self.venue or "").lower().strip()

        return (venue_normalized, time_str[:16], name_normalized)  # Compare up to minute precision

    class Config:
        json_schema_extra = {
            "example": {
                "venue": "Arc Community",
                "event_name": "Sauna & Ice Bath",
                "start_datetime": "2026-01-20T09:00:00Z",
                "end_datetime": "2026-01-20T10:30:00Z",
                "date": "2026-01-20",
                "location": "Hackney Wick, London",
                "price": "£25",
                "availability": "8 spots available",
                "capacity": 40,
                "spots_available": 8,
                "booking_url": "https://arc.marianatek.com/...",
                "instructor": "John Doe",
                "source": "arc_marianatek",
                "source_url": "https://arc.marianatek.com/api/...",
                "scraped_at": "2026-01-19T12:00:00Z",
            }
        }
