#!/usr/bin/env python3
"""
WellNest London Eventbrite scraper.

Scrapes events from WellNest London's Eventbrite organizer page
using the Eventbrite API.

Usage:
    export EVENTBRITE_TOKEN="your_token_here"
    python scrape_wellnest_eventbrite.py --out wellnest_events.json

Note: Requires EVENTBRITE_TOKEN environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests


ORGANIZER_ID = "113455047681"  # WellNest London
API_BASE = "https://www.eventbriteapi.com/v3"


def fetch_events(token: str, organizer_id: str) -> List[Dict[str, Any]]:
    """
    Fetch all live events for an Eventbrite organizer.

    Args:
        token: Eventbrite API token
        organizer_id: Eventbrite organizer ID

    Returns:
        List of event dictionaries
    """
    url = f"{API_BASE}/organizers/{organizer_id}/events/"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "status": "live",
        "expand": "venue",  # Include venue details
    }

    all_events = []
    page = 1

    while True:
        params["page"] = page
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            error_msg = response.json().get("error_description", "Unknown error")
            raise RuntimeError(
                f"Eventbrite API error (status {response.status_code}): {error_msg}"
            )

        data = response.json()
        events = data.get("events", [])

        if not events:
            break

        all_events.extend(events)

        # Check if there are more pages
        pagination = data.get("pagination", {})
        if not pagination.get("has_more_items", False):
            break

        page += 1

    return all_events


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize Eventbrite event data to our schema.

    Args:
        event: Raw Eventbrite event object

    Returns:
        Normalized event dictionary
    """
    # Extract name
    name = event.get("name", {})
    if isinstance(name, dict):
        title = name.get("text", "Unknown Event")
    else:
        title = str(name)

    # Extract start/end times
    start_obj = event.get("start", {})
    end_obj = event.get("end", {})
    start_dt = start_obj.get("local") or start_obj.get("utc")
    end_dt = end_obj.get("local") or end_obj.get("utc")

    # Extract date
    date_str = None
    if start_dt:
        # Format: "2026-02-15T10:00:00" -> "2026-02-15"
        date_str = start_dt[:10] if len(start_dt) >= 10 else None

    # Extract venue
    venue_obj = event.get("venue", {})
    venue_name = venue_obj.get("name") if venue_obj else None
    venue_address = None
    if venue_obj and venue_obj.get("address"):
        addr = venue_obj["address"]
        parts = []
        if addr.get("address_1"):
            parts.append(addr["address_1"])
        if addr.get("city"):
            parts.append(addr["city"])
        if addr.get("postal_code"):
            parts.append(addr["postal_code"])
        venue_address = ", ".join(parts) if parts else None

    # Extract description
    description = event.get("description", {})
    if isinstance(description, dict):
        description_text = description.get("text")
    else:
        description_text = None

    # Extract pricing
    is_free = event.get("is_free", False)
    price = "Free" if is_free else None

    # Extract capacity
    capacity = event.get("capacity")

    return {
        "source": "wellnest_eventbrite",
        "event_id": event.get("id"),
        "title": title,
        "start_datetime": start_dt,
        "end_datetime": end_dt,
        "date": date_str,
        "venue_name": venue_name,
        "venue_address": venue_address,
        "location": venue_address or venue_name,
        "url": event.get("url"),
        "description": description_text,
        "price": price,
        "capacity": capacity,
        "status": event.get("status"),
        "raw": event,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape WellNest London events from Eventbrite"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Eventbrite API token (or set EVENTBRITE_TOKEN env var)"
    )
    parser.add_argument(
        "--organizer-id",
        type=str,
        default=ORGANIZER_ID,
        help=f"Eventbrite organizer ID (default: {ORGANIZER_ID})"
    )

    args = parser.parse_args()

    # Get token from args or environment
    token = args.token or os.getenv("EVENTBRITE_TOKEN")
    if not token:
        print(
            "Error: EVENTBRITE_TOKEN not set. "
            "Either set the environment variable or use --token",
            file=sys.stderr
        )
        return 1

    try:
        # Fetch events
        print(f"Fetching events for organizer {args.organizer_id}...", file=sys.stderr)
        raw_events = fetch_events(token, args.organizer_id)

        # Normalize events
        events = [normalize_event(e) for e in raw_events]

        # Ensure output directory exists
        args.out.parent.mkdir(parents=True, exist_ok=True)

        # Write output
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

        print(f"✓ Scraped {len(events)} events", file=sys.stderr)
        print(f"✓ Output written to: {args.out}", file=sys.stderr)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
