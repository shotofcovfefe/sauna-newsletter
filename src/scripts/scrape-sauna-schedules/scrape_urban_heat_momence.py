#!/usr/bin/env python3
"""
Urban Heat Wellness Momence scraper.

Scrapes sauna sessions from Urban Heat Wellness using the Momence API.

Usage:
    python scrape_urban_heat_momence.py --out urban_heat_events.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


HOST_ID = "130322"  # Urban Heat Wellness
TEACHER_ID = "265017"  # Appears to be the sauna instructor/owner

DEFAULT_SESSION_TYPES = [
    "course-class",
    "fitness",
    "retreat",
    "special-event",
    "special-event-new",
]


def build_session() -> requests.Session:
    """Create a requests session with retry logic."""
    s = requests.Session()

    retry = Retry(
        total=6,
        connect=6,
        read=6,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    s.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (sauna-newsletter-scraper)",
            "Origin": "https://www.urbanheatwellness.com",
            "Referer": "https://www.urbanheatwellness.com/",
        }
    )
    return s


def fetch_events(
    session: requests.Session,
    host_id: str,
    teacher_id: str,
    from_date: str,
    page_size: int = 50,
    session_types: List[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch events from Urban Heat Wellness Momence API.

    Args:
        session: Requests session
        host_id: Momence host ID
        teacher_id: Momence teacher ID
        from_date: ISO timestamp (e.g., "2026-01-26T23:05:00.000Z")
        page_size: Number of events per page
        session_types: List of session types to include

    Returns:
        List of event dictionaries
    """
    if session_types is None:
        session_types = DEFAULT_SESSION_TYPES

    url = f"https://readonly-api.momence.com/host-plugins/host/{host_id}/host-schedule/sessions"

    params = {
        "teacherIds[]": teacher_id,
        "fromDate": from_date,
        "pageSize": str(page_size),
        "page": "0",
    }

    # Add session types
    for st in session_types:
        params[f"sessionTypes[]"] = st

    all_events = []
    page = 0

    while True:
        params["page"] = str(page)
        response = session.get(url, params=params, timeout=30)

        if response.status_code != 200:
            raise RuntimeError(
                f"HTTP {response.status_code} fetching page {page}: {response.text[:200]}"
            )

        data = response.json()
        events = data.get("payload", [])

        if not events:
            break

        all_events.extend(events)

        # Check if there are more pages
        pagination = data.get("pagination", {})
        if not pagination.get("hasMoreItems", False):
            break

        page += 1

    return all_events


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize Momence event data.

    Args:
        event: Raw Momence event object

    Returns:
        Normalized event dictionary
    """
    start_dt = event.get("startsAt")
    end_dt = event.get("endsAt")

    # Extract date
    date_str = None
    if start_dt:
        date_str = start_dt[:10] if len(start_dt) >= 10 else None

    # Calculate availability
    capacity = event.get("capacity")
    sold = event.get("ticketsSold", 0)
    spots_available = capacity - sold if capacity else None

    return {
        "source": "urban_heat_momence",
        "session_id": event.get("id"),
        "session_name": event.get("sessionName"),
        "start_datetime": start_dt,
        "end_datetime": end_dt,
        "date": date_str,
        "location": event.get("location"),
        "location_id": event.get("locationId"),
        "price": event.get("fixedTicketPrice"),
        "capacity": capacity,
        "tickets_sold": sold,
        "spots_available": spots_available,
        "teacher": event.get("teacher"),
        "teacher_id": event.get("teacherId"),
        "booking_url": event.get("link"),
        "status": event.get("status"),
        "raw": event,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Urban Heat Wellness events from Momence"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--host-id",
        type=str,
        default=HOST_ID,
        help=f"Momence host ID (default: {HOST_ID})"
    )
    parser.add_argument(
        "--teacher-id",
        type=str,
        default=TEACHER_ID,
        help=f"Momence teacher ID (default: {TEACHER_ID})"
    )

    args = parser.parse_args()

    try:
        # Generate from_date (current time in UTC)
        from_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # Fetch events
        print(f"Fetching events for host {args.host_id}...", file=sys.stderr)
        session = build_session()
        raw_events = fetch_events(
            session,
            args.host_id,
            args.teacher_id,
            from_date,
        )

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
