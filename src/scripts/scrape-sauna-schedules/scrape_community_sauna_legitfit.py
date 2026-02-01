#!/usr/bin/env python3
"""
Scrape Community Sauna booking "API" via LegitFit timetables.

What it does:
- Pulls Community Sauna location pages
- Extracts LegitFit timetable IDs
- Fetches LegitFit timetable HTML for a date range
- Parses sessions into structured JSON

Notes:
- This scrapes public HTML. If LegitFit later requires auth or blocks bots,
  you’ll need browser automation or an official API agreement.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


LEGITFIT_TIMETABLE_RE = re.compile(r"https://legitfit\.com/p/timetable/([a-f0-9]{24})", re.I)

DEFAULT_LOCATION_PAGES = [
    "https://www.community-sauna.co.uk/locations/camberwell#booking",
    "https://www.community-sauna.co.uk/locations/hackneywick#booking",
    # "https://www.community-sauna.co.uk/peckham-sauna",       # site uses mixed patterns
    "https://www.community-sauna.co.uk/stratford-sauna#booking",
    "https://www.community-sauna.co.uk/walthamstow-sauna#booking",
]

FALLBACK_SLUGS = {
    "stratford": ["communitysaunastratford"],
    "walthamstow": ["walthamstow"],
}


UA = "sauna-newsletter-bot/1.0 (+https://example.com; contact: you@example.com)"


@dataclasses.dataclass
class Session:
    location_name: str
    session_name: str
    start_time: str
    end_time: str
    duration_min: Optional[int]
    timezone_label: Optional[str]
    address: Optional[str]
    price_text: Optional[str]
    availability: Optional[str]
    date: str
    source_url: str


def http_get(url: str, timeout_s: int = 30) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout_s)
    r.raise_for_status()
    return r.text


def discover_legitfit_timetable_ids(location_pages: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for lp in location_pages:
        html = http_get(lp)
        ids = sorted(set(LEGITFIT_TIMETABLE_RE.findall(html)))

        if not ids:
            low = lp.lower()
            for key, slugs in FALLBACK_SLUGS.items():
                if key in low:
                    ids = slugs[:]
                    break

        out[lp] = ids
    return out


def build_timetable_url(timetable_id: str, day: date) -> str:
    # Observed pattern supports /<YYYY-MM-DD> with ?isIframe=true
    return f"https://legitfit.com/p/timetable/{timetable_id}/{day.isoformat()}?isIframe=true"


def parse_duration_min(s: str) -> Optional[int]:
    m = re.search(r"\|\s*(\d+)\s*MIN", s, re.I)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def parse_time_range(s: str) -> Optional[Tuple[str, str]]:
    # Example: "07:00 - 08:00 | 60 MIN (UTC)"
    m = re.search(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})", s)
    if not m:
        return None
    return m.group(1), m.group(2)


def parse_timezone_label(s: str) -> Optional[str]:
    m = re.search(r"\(([^)]+)\)\s*$", s.strip())
    return m.group(1) if m else None


def parse_legitfit_timetable(html: str, day: date, source_url: str) -> List[Session]:
    """
    LegitFit timetable HTML is fairly “texty”. We parse by walking line-by-line
    and detecting a repeating pattern:

      <Session Name>
      ###### <time-range> | <duration> (TZ)
      <description...>
      <availability>
      <address>
      <price line>

    This is resilient-ish without depending on brittle CSS classes.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]  # drop empties

    sessions: List[Session] = []
    location_name: str = "Unknown location"

    # First “location name” we see often appears as a standalone line near top
    # e.g. "Community Sauna Camberwell"
    for ln in lines[:80]:
        if ln.lower().startswith("community sauna"):
            location_name = ln
            break

    i = 0
    while i < len(lines):
        ln = lines[i]

        # Identify the time header line, then look backwards for the session title.
        if " - " in ln and " MIN" in ln and "|" in ln:
            time_range = parse_time_range(ln)
            if not time_range:
                i += 1
                continue

            start_time, end_time = time_range
            duration_min = parse_duration_min(ln)
            tz = parse_timezone_label(ln)

            # Title is typically the previous non-empty line
            if i == 0:
                i += 1
                continue
            session_name = lines[i - 1]

            # Now scan forward for availability/address/price-ish lines
            availability = None
            address = None
            price_text = None

            # Heuristics: within next ~12 lines after the time header
            for j in range(i + 1, min(i + 13, len(lines))):
                candidate = lines[j]

                # availability signals
                if candidate.lower() in {"sold out", "join waitlist", "bookings closed"}:
                    availability = candidate

                # address-ish: contains "UK" or looks like London postcode
                if (" UK" in candidate) or re.search(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", candidate):
                    # Avoid catching random marketing lines with postcodes; still good enough
                    address = candidate

                # price-ish: contains £ or "drop-in"
                if "£" in candidate or "drop-in" in candidate.lower():
                    price_text = candidate

            sessions.append(
                Session(
                    location_name=location_name,
                    session_name=session_name,
                    start_time=start_time,
                    end_time=end_time,
                    duration_min=duration_min,
                    timezone_label=tz,
                    address=address,
                    price_text=price_text,
                    availability=availability,
                    date=day.isoformat(),
                    source_url=source_url,
                )
            )

        i += 1

    return sessions


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output JSON file")
    ap.add_argument("--days", type=int, default=14, help="How many days to scrape starting today")
    ap.add_argument(
        "--locations",
        nargs="*",
        default=DEFAULT_LOCATION_PAGES,
        help="Community Sauna location page URLs (defaults to known ones)",
    )
    args = ap.parse_args()

    discovered = discover_legitfit_timetable_ids(args.locations)

    today = date.today()
    end_day = today + timedelta(days=args.days - 1)

    all_sessions: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for loc_page, timetable_ids in discovered.items():
        if not timetable_ids:
            errors.append({"location_page": loc_page, "error": "No LegitFit timetable IDs found"})
            continue

        # Some pages may contain multiple; scrape them all
        for tid in timetable_ids:
            d = today
            while d <= end_day:
                url = build_timetable_url(tid, d)
                try:
                    html = http_get(url)
                    sessions = parse_legitfit_timetable(html, d, url)
                    for s in sessions:
                        all_sessions.append(dataclasses.asdict(s))
                except Exception as e:
                    errors.append(
                        {"location_page": loc_page, "timetable_id": tid, "date": d.isoformat(), "url": url, "error": str(e)}
                    )
                d += timedelta(days=1)

    payload = {
        "scraped_at": date.today().isoformat(),
        "date_range": {"start": today.isoformat(), "end": end_day.isoformat()},
        "location_pages": args.locations,
        "discovered_timetable_ids": discovered,
        "session_count": len(all_sessions),
        "sessions": all_sessions,
        "errors": errors,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(all_sessions)} sessions to {args.out}")
    if errors:
        print(f"Encountered {len(errors)} errors (see output JSON).", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
