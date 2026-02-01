#!/usr/bin/env python3
"""
SweSauna event scraper.

Scrapes events from https://www.sweheatsauna.co.uk/events
and outputs structured JSON.

Usage:
    python scrape_swesauna.py --out swesauna_events.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE = "https://www.sweheatsauna.co.uk"
LIST_URL = f"{BASE}/events"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; sauna-newsletter-scraper/1.0)"
}

EVENT_PATH_RE = re.compile(r"^/events/[^?#]+$")


def fetch(url: str) -> str:
    """Fetch HTML from URL."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def extract_event_urls(list_html: str) -> List[str]:
    """Extract event URLs from the events list page."""
    soup = BeautifulSoup(list_html, "html.parser")
    urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if EVENT_PATH_RE.match(href):
            urls.add(urljoin(BASE, href))

    return sorted(urls)


def parse_event_page(event_url: str, html: str) -> Dict[str, Any]:
    """Parse a single event page and extract structured data."""
    soup = BeautifulSoup(html, "html.parser")

    # Title
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else None

    # Extract text for date/time parsing
    text = soup.get_text("\n", strip=True)
    date_line = None
    time_line = None
    range_line = None

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Find date/time after title
    if title and title in lines:
        start_idx = lines.index(title) + 1
    else:
        start_idx = 0

    window = lines[start_idx:start_idx + 40]

    # Heuristics for date/time extraction
    for ln in window:
        # Look for date patterns
        if re.search(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?\b", ln) and re.search(r"\b20\d{2}\b", ln):
            # Multi-day range or single day?
            if re.search(r"\b\d{1,2}:\d{2}\b", ln) and re.search(r"\bto\b|,\s*\d{1,2}\s+\w+\s+20\d{2}", ln):
                range_line = ln
            else:
                date_line = ln
        # Look for time range (e.g., "18:00 20:00")
        if re.fullmatch(r"\d{1,2}:\d{2}\s+\d{1,2}:\d{2}", ln):
            time_line = ln
        if date_line and time_line:
            break

    # Extract links (ICS calendar + booking)
    ics_url = None
    book_url = None
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True).lower()
        href = a["href"].strip()
        abs_url = urljoin(BASE, href)

        if label == "ics":
            ics_url = abs_url
        if "book now" in label:
            book_url = abs_url

    # Description: collect paragraphs until we hit "Location." (footer marker)
    desc_parts = []
    for p in soup.find_all(["p", "li", "h2", "h3"]):
        t = p.get_text(" ", strip=True)
        if not t:
            continue
        if t.strip().lower() == "location.":
            break
        # Skip navigation
        if t.strip().lower() in {"back to all events"}:
            continue
        # Avoid duplicating title/date/time
        if title and t == title:
            continue
        if date_line and t == date_line:
            continue
        if time_line and t == time_line:
            continue
        desc_parts.append(t)

    description = "\n".join(desc_parts).strip() or None

    return {
        "source": "swesauna",
        "url": event_url,
        "title": title,
        "date_line": date_line,
        "time_line": time_line,
        "range_line": range_line,
        "ics_url": ics_url,
        "book_url": book_url,
        "description": description,
    }


def scrape_swesauna() -> List[Dict[str, Any]]:
    """Scrape all events from SweSauna."""
    list_html = fetch(LIST_URL)
    event_urls = extract_event_urls(list_html)

    print(f"Found {len(event_urls)} event URLs", file=sys.stderr)

    events = []
    for i, url in enumerate(event_urls, 1):
        html = fetch(url)
        event = parse_event_page(url, html)
        events.append(event)

        # Be polite
        time.sleep(0.7)

        if i % 10 == 0:
            print(f"Fetched {i}/{len(event_urls)}", file=sys.stderr)

    return events


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape events from SweSauna (www.sweheatsauna.co.uk)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON file path"
    )

    args = parser.parse_args()

    try:
        events = scrape_swesauna()

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
        return 1


if __name__ == "__main__":
    sys.exit(main())
