#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple

import requests

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

BASE = "https://readonly-api.momence.com"
DEFAULT_HOST_ID = 47026
DEFAULT_TZ = "Europe/London"
DEFAULT_SESSION_TYPES = [
    "course-class",
    "fitness",
    "retreat",
    "special-event",
    "special-event-new",
]


def get_json(url: str, params: Dict[str, Any]) -> Any:
    r = requests.get(
        url,
        params=params,
        headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def extract_list(payload: Any) -> List[Dict[str, Any]]:
    """
    Your /sessions response is: {"payload":[{...}, ...]}
    Other Momence endpoints vary. Handle the common cases.
    """
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    if isinstance(payload, dict):
        for k in ("payload", "sessions", "data", "results", "items", "dates"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def normalize_dates_from_dates_payload(dates_payload: Any) -> List[str]:
    """
    Expected: {"dates":[{"sessionCount":18,"date":"2026-02-01"}, ...]}
    Return sorted unique YYYY-MM-DD strings.
    """
    out: List[str] = []

    if isinstance(dates_payload, dict) and isinstance(dates_payload.get("dates"), list):
        for x in dates_payload["dates"]:
            if isinstance(x, dict) and isinstance(x.get("date"), str):
                out.append(x["date"][:10])
            elif isinstance(x, str) and len(x) >= 10:
                out.append(x[:10])
    elif isinstance(dates_payload, list):
        for x in dates_payload:
            if isinstance(x, dict) and isinstance(x.get("date"), str):
                out.append(x["date"][:10])
            elif isinstance(x, str) and len(x) >= 10:
                out.append(x[:10])

    return sorted(set(d for d in out if d))


def pick_start_date(all_dates: List[str], now_utc: datetime, days: int) -> Tuple[str, List[str]]:
    today = now_utc.strftime("%Y-%m-%d")
    cutoff = (now_utc + timedelta(days=days)).strftime("%Y-%m-%d")
    in_range = [d for d in all_dates if today <= d <= cutoff]
    if in_range:
        return in_range[0], in_range
    if all_dates:
        return all_dates[0], []
    return today, []


def dedupe_sessions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for s in rows:
        sid = s.get("id")
        start = s.get("startsAt") or s.get("startDate") or s.get("startTime")
        key = (str(sid), str(start))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)
    return uniq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host-id", type=int, default=DEFAULT_HOST_ID)
    ap.add_argument("--tz", default=DEFAULT_TZ)
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--page-size", type=int, default=50)
    ap.add_argument("--out", required=True)
    ap.add_argument("--session-type", action="append", dest="session_types", default=[])
    args = ap.parse_args()

    session_types = args.session_types or DEFAULT_SESSION_TYPES
    scraped_at = datetime.now(timezone.utc)

    dates_url = f"{BASE}/host-plugins/host/{args.host_id}/host-schedule/dates"
    sessions_url = f"{BASE}/host-plugins/host/{args.host_id}/host-schedule/sessions"

    # dates
    dates_payload = get_json(
        dates_url,
        {
            "sessionTypes[]": session_types,
            "timeZone": args.tz,
        },
    )
    all_dates = normalize_dates_from_dates_payload(dates_payload)
    start_date, dates_in_range = pick_start_date(all_dates, scraped_at, args.days)

    # sessions (crawl from start_date)
    from_date = f"{start_date}T00:00:00.000Z"

    all_rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    page = 0
    while True:
        try:
            payload = get_json(
                sessions_url,
                {
                    "sessionTypes[]": session_types,
                    "fromDate": from_date,
                    "pageSize": args.page_size,
                    "page": page,
                    # harmless; some hosts use it
                    "timeZone": args.tz,
                },
            )
            rows = extract_list(payload)
            if not rows:
                break
            all_rows.extend(rows)
            page += 1
        except Exception as e:
            errors.append({"fromDate": from_date, "page": page, "error": str(e)})
            break

    uniq = dedupe_sessions(all_rows)

    # quick “description” normalisation: prefer `level` (your example), fall back to other keys
    # (we keep original session object too)
    normalized_sessions = []
    for s in uniq:
        normalized_sessions.append(
            {
                "id": s.get("id"),
                "hostId": s.get("hostId"),
                "name": s.get("sessionName"),
                "description": s.get("level") or s.get("description") or s.get("details"),
                "type": s.get("type"),
                "image": s.get("image"),
                "startsAt": s.get("startsAt"),
                "endsAt": s.get("endsAt"),
                "durationMinutes": s.get("durationMinutes"),
                "link": s.get("link"),
                "location": s.get("location"),
                "locationId": s.get("locationId"),
                "teacher": s.get("teacher"),
                "teacherId": s.get("teacherId"),
                "capacity": s.get("capacity"),
                "ticketsSold": s.get("ticketsSold"),
                "fixedTicketPrice": s.get("fixedTicketPrice"),
                "currency": s.get("currency"),
                "raw": s,
            }
        )

    out = {
        "scraped_at": scraped_at.isoformat(),
        "host_id": args.host_id,
        "timezone": args.tz,
        "session_types": session_types,
        "date_range": {
            "today_utc": scraped_at.strftime("%Y-%m-%d"),
            "days": args.days,
            "start_date_used_for_sessions": start_date,
            "dates_in_range": dates_in_range,
        },
        "dates_raw": dates_payload,
        "dates_all": all_dates,
        "session_count": len(normalized_sessions),
        "sessions": normalized_sessions,
        "errors": errors,
        "endpoints": {"dates": dates_url, "sessions": sessions_url},
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(
        f"Wrote {args.out} (sessions={len(normalized_sessions)}, pages={page}, start_date={start_date}, errors={len(errors)})"
    )


if __name__ == "__main__":
    main()
