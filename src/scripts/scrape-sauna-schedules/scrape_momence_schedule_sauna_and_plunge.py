#!/usr/bin/env python3
"""
Scrape Momence readonly host schedule sessions.

Example:
  python scrape_momence_schedule.py \
    --host-id 99521 \
    --from-date "2026-01-14T21:30:00.000Z" \
    --page-size 200 \
    --out sessions.json

Notes:
- Uses the readonly-api endpoint you provided.
- Paginates until it runs out of results.
- Saves a single JSON file with metadata + all sessions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_SESSION_TYPES = [
    "course-class",
    "fitness",
    "retreat",
    "special-event",
    "special-event-new",
]


@dataclass
class FetchConfig:
    host_id: int
    from_date: str
    page_size: int
    session_types: List[str]
    timeout_s: float
    sleep_s: float
    max_pages: Optional[int]


def build_session() -> requests.Session:
    s = requests.Session()

    # Reasonable retry policy for flaky networks / transient 5xx
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

    # Headers: look like a normal browser client
    s.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Origin": "https://momence.com",
            "Referer": "https://momence.com/",
        }
    )
    return s


def fetch_page(
    session: requests.Session,
    cfg: FetchConfig,
    page: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (items, raw_json).
    We try to find a list of sessions in the response. If shape differs,
    we fall back to scanning common keys.
    """
    url = f"https://readonly-api.momence.com/host-plugins/host/{cfg.host_id}/host-schedule/sessions"
    params: List[Tuple[str, str]] = []
    for st in cfg.session_types:
        params.append(("sessionTypes[]", st))
    params.extend(
        [
            ("fromDate", cfg.from_date),
            ("pageSize", str(cfg.page_size)),
            ("page", str(page)),
        ]
    )

    r = session.get(url, params=params, timeout=cfg.timeout_s)
    if r.status_code >= 400:
        # Include body excerpt for debugging
        excerpt = (r.text or "")[:500]
        raise RuntimeError(f"HTTP {r.status_code} fetching page={page}. Body: {excerpt}")

    data = r.json()

    # Common shapes: either list directly, or {data: [...]}, or {sessions: [...]}, or {payload: [...]} etc.
    items: Optional[List[Dict[str, Any]]] = None
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("payload", "data", "sessions", "items", "results"):
            if key in data and isinstance(data[key], list):
                items = data[key]
                break

    if items is None:
        raise RuntimeError(
            f"Unexpected JSON shape on page={page}. Top-level type={type(data).__name__}. "
            f"Top-level keys={list(data.keys()) if isinstance(data, dict) else 'n/a'}"
        )

    # Ensure dict-ish items
    items = [x for x in items if isinstance(x, dict)]
    return items, data


def scrape_all(cfg: FetchConfig) -> Dict[str, Any]:
    session = build_session()
    all_items: List[Dict[str, Any]] = []
    pages_fetched = 0
    page = 0

    while True:
        if cfg.max_pages is not None and page >= cfg.max_pages:
            break

        items, raw = fetch_page(session, cfg, page)
        pages_fetched += 1

        if not items:
            break

        all_items.extend(items)

        # Heuristic: if we got fewer than page_size, likely last page
        if len(items) < cfg.page_size:
            break

        page += 1
        if cfg.sleep_s > 0:
            time.sleep(cfg.sleep_s)

    return {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "host_id": cfg.host_id,
        "from_date": cfg.from_date,
        "page_size": cfg.page_size,
        "session_types": cfg.session_types,
        "pages_fetched": pages_fetched,
        "count": len(all_items),
        "sessions": all_items,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape Momence readonly schedule sessions.")
    p.add_argument("--host-id", type=int, required=True, help="Momence host id (e.g. 99521).")
    p.add_argument(
        "--from-date",
        required=True,
        help='ISO string used by Momence API, e.g. "2026-01-14T21:30:00.000Z"',
    )
    p.add_argument("--page-size", type=int, default=200, help="Page size (default: 200).")
    p.add_argument(
        "--session-type",
        dest="session_types",
        action="append",
        default=[],
        help="Repeatable. If omitted, uses common defaults.",
    )
    p.add_argument("--timeout", type=float, default=20.0, help="Request timeout seconds.")
    p.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Sleep between pages (seconds). Helps avoid 429s.",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional cap for pages (useful for testing).",
    )
    p.add_argument("--out", required=True, help="Output JSON path.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    session_types = args.session_types or DEFAULT_SESSION_TYPES

    cfg = FetchConfig(
        host_id=args.host_id,
        from_date=args.from_date,
        page_size=args.page_size,
        session_types=session_types,
        timeout_s=args.timeout,
        sleep_s=args.sleep,
        max_pages=args.max_pages,
    )

    try:
        payload = scrape_all(cfg)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote {args.out} (sessions={payload['count']}, pages={payload['pages_fetched']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
