#!/usr/bin/env python3
"""
Sauna Social Club scraper.

Scrapes events from https://www.saunasocialclub.co.uk/whats-on
and outputs structured JSON.

Usage:
    python scrape_sauna_social_club.py --out sauna_social_club_events.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


URL = "https://www.saunasocialclub.co.uk/whats-on"
TZ = dt.timezone.utc

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}

WEEKDAYS = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6
}

EVENT_RE = re.compile(
    r"^(?P<weekday>[A-Za-z]{3,6})\s+(?P<day>\d{1,2})\s*\|\s*(?P<title>.+?)\s*$"
)


def infer_date(month: int, day: int, weekday_idx: int, today: dt.date) -> Optional[dt.date]:
    """
    Infer the real calendar date by matching weekday.
    Searches nearby years and chooses the date closest to today,
    with a bias toward future dates.
    """
    candidates = []
    for year in [today.year - 1, today.year, today.year + 1, today.year + 2]:
        try:
            d = dt.date(year, month, day)
        except ValueError:
            continue
        if d.weekday() == weekday_idx:
            candidates.append(d)

    if not candidates:
        return None

    # Prefer dates not too far in the past
    def score(d: dt.date) -> tuple:
        delta_days = (d - today).days
        # Allow up to 7 days past without penalty
        future_penalty = 0 if delta_days >= -7 else 1
        return (future_penalty, abs(delta_days))

    return sorted(candidates, key=score)[0]


def fetch_html(url: str) -> str:
    """Fetch HTML from URL."""
    r = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (sauna-newsletter-scraper)"}
    )
    r.raise_for_status()
    return r.text


def scrape_whats_on(url: str = URL) -> List[Dict]:
    """
    Scrape events from Sauna Social Club's What's On page.

    Returns list of event dictionaries.
    """
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    # Gather block-level text elements in document order
    lines: List[Tag] = []
    for el in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        txt = el.get_text(" ", strip=True)
        if txt:
            lines.append(el)

    today = dt.datetime.now(TZ).date()
    current_month: Optional[str] = None
    events: List[Dict] = []

    for el in lines:
        text = el.get_text(" ", strip=True)

        # Check if this is a month header
        low = text.strip().lower()
        if low in MONTHS:
            current_month = low
            continue

        # Only parse event lines when we're inside a month section
        if not current_month:
            continue

        # Try to match event pattern: "Thu 23 | Event Name"
        m = EVENT_RE.match(text)
        if not m:
            continue

        weekday_raw = m.group("weekday").strip().lower()
        day = int(m.group("day"))
        title = m.group("title").strip()

        # Normalize weekday
        weekday_idx = WEEKDAYS.get(weekday_raw)
        if weekday_idx is None:
            # Try first 3 letters
            weekday_idx = WEEKDAYS.get(weekday_raw[:3])

        # Infer the actual date
        month_num = MONTHS[current_month]
        date_val = infer_date(month_num, day, weekday_idx, today) if weekday_idx is not None else None

        # Find any external booking link (e.g. Outsavvy)
        external_url = None
        a = el.find("a", href=True)
        if a:
            external_url = urljoin(url, a["href"])

        events.append({
            "source": "saunasocialclub",
            "source_url": url,
            "month": current_month.title(),
            "weekday": m.group("weekday"),
            "day": day,
            "inferred_date": date_val.isoformat() if date_val else None,
            "title": title,
            "booking_url": external_url or "https://www.saunasocialclub.co.uk/book",
            "external_booking_url": external_url,
        })

    return events


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape events from Sauna Social Club"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON file path"
    )

    args = parser.parse_args()

    try:
        events = scrape_whats_on()

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
