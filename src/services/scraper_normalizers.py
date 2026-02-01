#!/usr/bin/env python3
"""
Normalization adapters to convert each scraper's output format into ScrapedEvent models.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.models.scraped_event import ScrapedEvent


def normalize_arc_marianatek(raw_data: List[Dict[str, Any]], scraped_at: str) -> List[ScrapedEvent]:
    """
    Normalize Arc Marianatek API output.
    Expected input: List of class objects with id, name, start_at, etc.
    """
    events = []
    for item in raw_data:
        # Handle both flat structure and nested "raw" structure
        raw = item.get("raw", item)

        # Prefer booking_start_datetime from raw (has full date), fallback to start_at (time only)
        start_at = raw.get("booking_start_datetime") or item.get("start_at")
        end_at = item.get("end_at") or raw.get("end_at")

        events.append(
            ScrapedEvent(
                venue="Arc Community",
                event_name=item.get("name", "Unknown Event"),
                start_datetime=start_at,
                end_datetime=end_at,
                date=start_at[:10] if start_at and len(start_at) >= 10 else None,
                location="Hackney Wick, London",
                capacity=item.get("capacity"),
                spots_available=item.get("spots_available") or raw.get("available_spot_count"),
                booking_url=item.get("booking_url"),
                instructor=item.get("instructor_name"),
                source="arc_marianatek",
                source_url=item.get("source_url"),
                scraped_at=scraped_at,
                raw=raw,
            )
        )
    return events


def normalize_community_sauna_legitfit(data: Dict[str, Any], scraped_at: str) -> List[ScrapedEvent]:
    """
    Normalize Community Sauna LegitFit scraper output.
    Expected input: Dict with "sessions" list.
    """
    events = []
    sessions = data.get("sessions", [])

    for session in sessions:
        # Combine date with start_time to make a datetime
        date_str = session.get("date", "")
        start_time = session.get("start_time", "")
        end_time = session.get("end_time", "")

        start_dt = f"{date_str}T{start_time}:00" if date_str and start_time else None
        end_dt = f"{date_str}T{end_time}:00" if date_str and end_time else None

        events.append(
            ScrapedEvent(
                venue=session.get("location_name", "Community Sauna"),
                event_name=session.get("session_name", "Unknown Session"),
                start_datetime=start_dt,
                end_datetime=end_dt,
                date=date_str,
                location=session.get("address"),
                price=session.get("price_text"),
                availability=session.get("availability"),
                source="community_sauna_legitfit",
                source_url=session.get("source_url"),
                scraped_at=scraped_at,
                raw=session,
            )
        )
    return events


def normalize_rebase_mindbody(data: Dict[str, Any], scraped_at: str) -> List[ScrapedEvent]:
    """
    Normalize Rebase Mindbody widget scraper output.
    Expected input: Dict with "instances" list.
    """
    import re
    events = []
    instances = data.get("instances", [])

    for inst in instances:
        # Extract date from source_date field
        date_str = inst.get("source_date", "")

        # Parse start time - format: "7:00 AM – 7:45 AM GMT View details Hide details"
        start_raw = inst.get("start", "")
        start_dt = None

        if start_raw and date_str:
            # Extract just the start time (before the dash)
            time_match = re.match(r"(\d{1,2}:\d{2}\s*[AP]M)", start_raw)
            if time_match:
                time_str = time_match.group(1)
                # Combine date and time
                # Convert "7:00 AM" format to ISO
                from datetime import datetime
                try:
                    dt_obj = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
                    start_dt = dt_obj.strftime("%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    pass

        events.append(
            ScrapedEvent(
                venue="Rebase Recovery",
                event_name=inst.get("title", "Unknown Class"),
                start_datetime=start_dt,
                end_datetime=inst.get("end"),
                date=date_str,
                location=inst.get("location", "London"),
                booking_url=inst.get("signup_url"),
                instructor=inst.get("instructor"),
                source="rebase_mindbody",
                source_url=inst.get("source_url"),
                scraped_at=scraped_at,
                raw=inst,
            )
        )
    return events


def normalize_momence_schedule(data: Dict[str, Any], scraped_at: str, venue_name: str = "Sauna & Plunge") -> List[ScrapedEvent]:
    """
    Normalize Momence schedule scraper output.
    Expected input: Dict with "sessions" list.

    Note: Filters to only include sessions at "Sauna & Plunge" location,
    excluding "The Studio" fitness classes.
    """
    events = []
    sessions = data.get("sessions", [])

    for session in sessions:
        # Filter: Only include sessions at "Sauna & Plunge" location
        # (Skip "The Studio" fitness/pilates classes)
        location = session.get("location") or session.get("locationName") or ""
        if location.lower() != "sauna & plunge":
            continue

        # Momence typically has rich session objects
        start_dt = session.get("startsAt") or session.get("startDate") or session.get("start_at")
        end_dt = session.get("endsAt") or session.get("endDate") or session.get("end_at")

        # Extract pricing if available
        price = None
        if "fixedTicketPrice" in session and session["fixedTicketPrice"]:
            price = f"£{session['fixedTicketPrice']}"
        elif "price" in session and session["price"]:
            price = f"£{session['price']}" if isinstance(session["price"], (int, float)) else str(session["price"])
        elif "pricing" in session:
            price = str(session["pricing"])

        # Availability
        availability = None
        spots_avail = session.get("spotsAvailable") or session.get("availableSpots")
        capacity = session.get("capacity") or session.get("maxCapacity")
        if spots_avail is not None:
            availability = f"{spots_avail} spots available"

        events.append(
            ScrapedEvent(
                venue=venue_name,
                event_name=session.get("sessionName") or session.get("name") or session.get("title", "Unknown Session"),
                start_datetime=start_dt,
                end_datetime=end_dt,
                date=start_dt[:10] if start_dt and len(start_dt) >= 10 else None,
                location=location,
                price=price,
                availability=availability,
                capacity=capacity,
                spots_available=spots_avail,
                booking_url=session.get("link") or session.get("bookingUrl") or session.get("url"),
                instructor=session.get("teacher") or session.get("instructor") or session.get("instructorName"),
                source="momence_schedule",
                scraped_at=scraped_at,
                raw=session,
            )
        )
    return events


def normalize_rooftop_saunas(data: Dict[str, Any], scraped_at: str) -> List[ScrapedEvent]:
    """
    Normalize Rooftop Saunas scraper output.
    Expected input: Dict with "ranked_candidates" or similar structure.

    Note: This scraper sniffs endpoints, so the structure may vary.
    We'll do best-effort extraction.
    """
    events = []

    # If this is the sniff output, we need to look at actual session data
    # This will need adjustment based on actual replay data structure
    if "json" in data:
        # This is replay output
        session_data = data.get("json", {})
        if isinstance(session_data, list):
            sessions = session_data
        elif isinstance(session_data, dict):
            sessions = session_data.get("sessions", []) or session_data.get("data", [])
        else:
            sessions = []

        for session in sessions:
            if not isinstance(session, dict):
                continue

            events.append(
                ScrapedEvent(
                    venue="Rooftop Saunas",
                    event_name=session.get("name") or session.get("title", "Unknown Event"),
                    start_datetime=session.get("start") or session.get("startTime"),
                    end_datetime=session.get("end") or session.get("endTime"),
                    date=session.get("date"),
                    location=session.get("location", "London"),
                    price=session.get("price"),
                    availability=session.get("availability"),
                    capacity=session.get("capacity"),
                    spots_available=session.get("spotsAvailable"),
                    booking_url=session.get("bookingUrl") or data.get("url"),
                    source="rooftop_saunas",
                    scraped_at=scraped_at,
                    raw=session,
                )
            )

    return events


def normalize_urban_heat_momence(data: List[Dict[str, Any]], scraped_at: str) -> List[ScrapedEvent]:
    """
    Normalize Urban Heat Wellness Momence scraper output.
    Expected input: List of normalized Momence event objects.
    """
    events = []

    for item in data:
        # Calculate availability text
        availability = None
        spots_avail = item.get("spots_available")
        capacity = item.get("capacity")
        if spots_avail is not None and capacity:
            availability = f"{spots_avail}/{capacity} spots available"

        # Format price
        price = None
        if item.get("price"):
            price = f"£{item['price']}"

        events.append(
            ScrapedEvent(
                venue="Urban Heat Wellness",
                event_name=item.get("session_name", "Unknown Session"),
                start_datetime=item.get("start_datetime"),
                end_datetime=item.get("end_datetime"),
                date=item.get("date"),
                location=item.get("location") or "London",
                price=price,
                capacity=capacity,
                spots_available=spots_avail,
                availability=availability,
                booking_url=item.get("booking_url"),
                instructor=item.get("teacher"),
                source="urban_heat_momence",
                scraped_at=scraped_at,
                raw=item,
            )
        )

    return events


def normalize_andsoul_momence(data: Dict[str, Any], scraped_at: str) -> List[ScrapedEvent]:
    """
    Normalize And Soul Momence scraper output.
    Expected input: Dict with "sessions" list containing Momence API session objects.

    Note: Filters to only include sessions at "Sauna" location,
    excluding yoga, breathwork, and other wellness classes.
    """
    events = []
    sessions = data.get("sessions", [])

    for session in sessions:
        # Filter: Only include sessions at "Sauna" location
        # (Skip Heart, Mind, Soul, Body rooms which are yoga/fitness)
        location = session.get("location") or ""
        if location.lower() != "sauna":
            continue

        # Extract fields from normalized Momence session object
        start_dt = session.get("startsAt")
        end_dt = session.get("endsAt")

        # Calculate date from start datetime
        date_str = start_dt[:10] if start_dt and len(start_dt) >= 10 else None

        # Format price
        price = None
        if session.get("fixedTicketPrice"):
            currency = session.get("currency", "£")
            price = f"{currency}{session['fixedTicketPrice']}"

        # Calculate availability
        availability = None
        capacity = session.get("capacity")
        tickets_sold = session.get("ticketsSold")
        if capacity and tickets_sold is not None:
            spots_avail = capacity - tickets_sold
            availability = f"{spots_avail}/{capacity} spots available"

        events.append(
            ScrapedEvent(
                venue="And Soul",
                event_name=session.get("name", "Unknown Session"),
                start_datetime=start_dt,
                end_datetime=end_dt,
                date=date_str,
                location=location,
                price=price,
                capacity=capacity,
                spots_available=capacity - tickets_sold if capacity and tickets_sold is not None else None,
                availability=availability,
                booking_url=session.get("link"),
                instructor=session.get("teacher"),
                description=session.get("description"),
                source="andsoul_momence",
                scraped_at=scraped_at,
                raw=session,
            )
        )

    return events


def normalize_wellnest_eventbrite(data: List[Dict[str, Any]], scraped_at: str) -> List[ScrapedEvent]:
    """
    Normalize WellNest Eventbrite scraper output.
    Expected input: List of normalized Eventbrite event objects.
    """
    events = []

    for item in data:
        events.append(
            ScrapedEvent(
                venue="WellNest London",
                event_name=item.get("title", "Unknown Event"),
                start_datetime=item.get("start_datetime"),
                end_datetime=item.get("end_datetime"),
                date=item.get("date"),
                location=item.get("location") or item.get("venue_name") or "London",
                price=item.get("price"),
                capacity=item.get("capacity"),
                booking_url=item.get("url"),
                description=item.get("description"),
                source="wellnest_eventbrite",
                source_url=item.get("url"),
                scraped_at=scraped_at,
                raw=item,
            )
        )

    return events


def normalize_sauna_social_club(data: List[Dict[str, Any]], scraped_at: str) -> List[ScrapedEvent]:
    """
    Normalize Sauna Social Club scraper output.
    Expected input: List of event objects with inferred_date, title, etc.
    """
    events = []

    for item in data:
        # Sauna Social Club provides inferred dates
        date_str = item.get("inferred_date")
        start_dt = None
        end_dt = None

        # If we have a date, we could potentially extract times from title
        # For now, just use the date
        if date_str:
            # No specific times provided, so leave as date-only events
            pass

        events.append(
            ScrapedEvent(
                venue="Sauna Social Club",
                event_name=item.get("title", "Unknown Event"),
                start_datetime=start_dt,
                end_datetime=end_dt,
                date=date_str,
                location="London",
                booking_url=item.get("external_booking_url") or item.get("booking_url"),
                source="sauna_social_club",
                source_url=item.get("source_url"),
                scraped_at=scraped_at,
                raw=item,
            )
        )

    return events


def normalize_swesauna(data: List[Dict[str, Any]], scraped_at: str) -> List[ScrapedEvent]:
    """
    Normalize SweSauna scraper output.
    Expected input: List of event objects with title, date_line, time_line, etc.
    """
    import re

    events = []

    for item in data:
        # SweSauna outputs raw date/time strings that need parsing
        # date_line: "Sunday 25 January 2026"
        # time_line: "18:00 20:00" (may be in description)
        # range_line: "Wed, 31 Dec 2025 20:00 Thu, 1 Jan 2026 01:00"

        date_str = None
        start_dt = None
        end_dt = None

        # First try: date_line from field
        if item.get("date_line"):
            date_line = item["date_line"]
            try:
                date_obj = None
                for fmt in ["%A %d %B %Y", "%a %d %B %Y", "%d %B %Y"]:
                    try:
                        date_obj = datetime.strptime(date_line, fmt)
                        break
                    except ValueError:
                        continue

                if date_obj:
                    date_str = date_obj.strftime("%Y-%m-%d")
            except Exception:
                pass

        # Try to get times from time_line or description
        if item.get("time_line"):
            time_line = item["time_line"]
            time_parts = time_line.split()
            if len(time_parts) >= 2 and date_str:
                start_time = time_parts[0]
                end_time = time_parts[1]
                start_dt = f"{date_str}T{start_time}:00"
                end_dt = f"{date_str}T{end_time}:00"

        # Extract date and time from description if not already found
        if item.get("description"):
            desc = item["description"]
            lines = [ln.strip() for ln in desc.splitlines() if ln.strip()]

            # Look for date pattern in first few lines (if not already found)
            if not date_str:
                for ln in lines[:10]:
                    date_match = re.search(r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})", ln)
                    if date_match:
                        date_line = date_match.group(1)
                        try:
                            date_obj = datetime.strptime(date_line, "%A %d %B %Y")
                            date_str = date_obj.strftime("%Y-%m-%d")
                        except ValueError:
                            pass
                        break

            # Look for time pattern "19:00 23:00" (if not already found)
            if date_str and not start_dt:
                for ln in lines[:10]:
                    time_match = re.search(r"(\d{1,2}:\d{2})\s+(\d{1,2}:\d{2})", ln)
                    if time_match:
                        start_time = time_match.group(1)
                        end_time = time_match.group(2)
                        start_dt = f"{date_str}T{start_time}:00"
                        end_dt = f"{date_str}T{end_time}:00"
                        break

        events.append(
            ScrapedEvent(
                venue="SweSauna",
                event_name=item.get("title", "Unknown Event"),
                start_datetime=start_dt,
                end_datetime=end_dt,
                date=date_str,
                location="Royal Victoria Dock, London",
                booking_url=item.get("book_url"),
                description=item.get("description"),
                source="swesauna",
                source_url=item.get("url"),
                scraped_at=scraped_at,
                raw=item,
            )
        )

    return events


def load_and_normalize(file_path: Path, scraper_type: str) -> List[ScrapedEvent]:
    """
    Load a scraper output file and normalize it to ScrapedEvent objects.

    Args:
        file_path: Path to the JSON output file
        scraper_type: Type of scraper ('arc_marianatek', 'community_sauna', etc.)

    Returns:
        List of normalized ScrapedEvent objects
    """
    if not file_path.exists():
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scraped_at = datetime.now(timezone.utc).isoformat()

    # Route to appropriate normalizer
    if scraper_type == "arc_marianatek":
        if isinstance(data, list):
            return normalize_arc_marianatek(data, scraped_at)
        return []

    elif scraper_type == "community_sauna_legitfit":
        return normalize_community_sauna_legitfit(data, scraped_at)

    elif scraper_type == "rebase_mindbody":
        return normalize_rebase_mindbody(data, scraped_at)

    elif scraper_type == "momence_schedule":
        return normalize_momence_schedule(data, scraped_at)

    elif scraper_type == "rooftop_saunas":
        return normalize_rooftop_saunas(data, scraped_at)

    elif scraper_type == "swesauna":
        if isinstance(data, list):
            return normalize_swesauna(data, scraped_at)
        return []

    elif scraper_type == "sauna_social_club":
        if isinstance(data, list):
            return normalize_sauna_social_club(data, scraped_at)
        return []

    elif scraper_type == "wellnest_eventbrite":
        if isinstance(data, list):
            return normalize_wellnest_eventbrite(data, scraped_at)
        return []

    elif scraper_type == "urban_heat_momence":
        if isinstance(data, list):
            return normalize_urban_heat_momence(data, scraped_at)
        return []

    elif scraper_type == "andsoul_momence":
        return normalize_andsoul_momence(data, scraped_at)

    else:
        raise ValueError(f"Unknown scraper type: {scraper_type}")
