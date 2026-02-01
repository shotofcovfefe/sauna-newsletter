#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode

import requests


BASE = "https://arc.marianatek.com"
CLASSES_PATH = "/api/customer/v1/classes"

DEFAULT_REGION = 48541
DEFAULT_LOCATION = 48717


@dataclass
class ArcClass:
    # Raw-ish fields (keep for traceability)
    id: Any
    name: Optional[str]
    start_at: Optional[str]
    end_at: Optional[str]
    location_id: Optional[int]
    region_id: Optional[int]
    instructor_name: Optional[str]
    capacity: Optional[int]
    spots_available: Optional[int]
    booking_url: Optional[str]
    raw: Dict[str, Any]


def _iso(d: date) -> str:
    return d.isoformat()


def _guess_booking_url(class_obj: Dict[str, Any]) -> Optional[str]:
    """
    Mariana Tek often includes a booking URL or slugs; if it doesn't, we can at least
    link users to the schedule page.
    """
    for k in ["booking_url", "url", "web_url", "public_url"]:
        v = class_obj.get(k)
        if isinstance(v, str) and v.startswith("http"):
            return v
    # Fallback: no per-class URL known from this response
    return None


def _extract_instructor(class_obj: Dict[str, Any]) -> Optional[str]:
    # Try a few common shapes
    inst = class_obj.get("instructor") or class_obj.get("trainer") or class_obj.get("coach")
    if isinstance(inst, dict):
        for k in ["name", "full_name", "display_name"]:
            if isinstance(inst.get(k), str):
                return inst[k]
    if isinstance(class_obj.get("instructor_name"), str):
        return class_obj["instructor_name"]
    return None


def _extract_capacity(class_obj: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    cap = class_obj.get("capacity")
    avail = class_obj.get("spots_available") or class_obj.get("available_spots") or class_obj.get("spotsRemaining")
    def to_int(x):
        try:
            return int(x)
        except Exception:
            return None
    return to_int(cap), to_int(avail)


def fetch_classes(
    session: requests.Session,
    region: int,
    location: int,
    min_date: date,
    max_date: date,
    page_size: int = 500,
) -> List[Dict[str, Any]]:
    """
    Fetch raw class objects from Mariana Tek customer API.

    Note: We use the same query params you captured from the website.
    If Mariana Tek ever adds pagination, we can extend this based on response shape.
    """
    params = {
        "min_start_date": _iso(min_date),
        "max_start_date": _iso(max_date),
        "page_size": page_size,
        "location": location,
        "region": region,
    }
    url = f"{BASE}{CLASSES_PATH}?{urlencode(params)}"

    r = session.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()

    # Response shape varies; handle the common ones.
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["classes", "data", "results", "items"]:
            if isinstance(data.get(key), list):
                return data[key]
    raise RuntimeError(f"Unexpected response shape from {url}: {type(data)}")


def normalise(raw_classes: List[Dict[str, Any]], region: int, location: int) -> List[ArcClass]:
    out: List[ArcClass] = []
    for c in raw_classes:
        start_at = c.get("start_at") or c.get("start_time") or c.get("starts_at") or c.get("start")
        end_at = c.get("end_at") or c.get("end_time") or c.get("ends_at") or c.get("end")
        cap, avail = _extract_capacity(c)

        out.append(
            ArcClass(
                id=c.get("id") or c.get("class_id"),
                name=c.get("name") or c.get("title"),
                start_at=start_at,
                end_at=end_at,
                location_id=c.get("location_id") or location,
                region_id=c.get("region_id") or region,
                instructor_name=_extract_instructor(c),
                capacity=cap,
                spots_available=avail,
                booking_url=_guess_booking_url(c),
                raw=c,
            )
        )
    return out


def to_rows(classes: List[ArcClass]) -> List[Dict[str, Any]]:
    rows = []
    for cl in classes:
        rows.append(
            {
                "id": cl.id,
                "name": cl.name,
                "start_at": cl.start_at,
                "end_at": cl.end_at,
                "region_id": cl.region_id,
                "location_id": cl.location_id,
                "instructor_name": cl.instructor_name,
                "capacity": cl.capacity,
                "spots_available": cl.spots_available,
                "booking_url": cl.booking_url,
            }
        )
    return rows


def write_json(path: Path, classes: List[ArcClass]) -> None:
    payload = [asdict(c) for c in classes]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", type=int, default=DEFAULT_REGION)
    ap.add_argument("--location", type=int, default=DEFAULT_LOCATION)
    ap.add_argument("--days", type=int, default=14, help="How many days ahead to fetch (inclusive).")
    ap.add_argument("--start", type=str, default=None, help="YYYY-MM-DD (overrides --days)")
    ap.add_argument("--end", type=str, default=None, help="YYYY-MM-DD (overrides --days)")
    ap.add_argument("--out-json", type=Path, default=Path("arc_classes.json"))
    ap.add_argument("--out-csv", type=Path, default=None)
    args = ap.parse_args()

    if args.start and args.end:
        min_d = date.fromisoformat(args.start)
        max_d = date.fromisoformat(args.end)
    else:
        min_d = date.today()
        max_d = min_d + timedelta(days=max(args.days - 1, 0))

    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
    )

    raw = fetch_classes(
        session=s,
        region=args.region,
        location=args.location,
        min_date=min_d,
        max_date=max_d,
    )
    classes = normalise(raw, region=args.region, location=args.location)

    # Sort by start time if possible
    def sort_key(x: ArcClass):
        try:
            return datetime.fromisoformat((x.start_at or "").replace("Z", "+00:00"))
        except Exception:
            return datetime.max

    classes.sort(key=sort_key)

    write_json(args.out_json, classes)
    print(f"Wrote {len(classes)} classes to {args.out_json}")

    if args.out_csv:
        rows = to_rows(classes)
        write_csv(args.out_csv, rows)
        print(f"Wrote CSV to {args.out_csv}")


if __name__ == "__main__":
    main()
