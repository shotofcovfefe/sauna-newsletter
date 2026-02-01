#!/usr/bin/env python3
"""
Sniff booking API calls for Arc by capturing *all* XHR/fetch requests + JSON-ish responses
from the /book-now page, then replay one endpoint.

Why:
- Booking widgets often fail silently under automation; your earlier script saw 0 calls
  because it filtered too narrowly (api.momence.com).
- This captures everything and shows you the actual booking provider + endpoint.

Install:
  pip install playwright requests
  playwright install chromium

Usage:
  python src/scripts/scrape_arc_momence.py sniff --out discovered.json
  python src/scripts/scrape_arc_momence.py fetch --in discovered.json --pick 0 --out data.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ARC_URL = (
    "https://www.arc-community.com/book-now"
    "?_mt=%2Fschedule%2Fdaily%2F48541%3Flocations%3D48717"
    "&ref=https%3A%2F%2Fwww.google.com%2F"
)

# Heuristics to rank likely schedule endpoints
LIKELY_KEYWORDS = re.compile(
    r"(schedule|sessions|session|events|event|classes|class|calendar|timetable|timeslot|booking|bookings)",
    re.I,
)


@dataclass
class Captured:
    url: str
    method: str
    resource_type: str
    status: Optional[int] = None
    content_type: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "resource_type": self.resource_type,
            "status": self.status,
            "content_type": self.content_type,
        }

    @staticmethod
    def from_json(d: Dict[str, Any]) -> "Captured":
        return Captured(
            url=d["url"],
            method=d["method"],
            resource_type=d.get("resource_type", ""),
            status=d.get("status"),
            content_type=d.get("content_type"),
        )


def sniff(out_path: Path, seconds: int = 20) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Missing playwright. Install: pip install playwright", file=sys.stderr)
        raise

    # Use a persistent profile so cookies/consent survive reruns.
    user_data_dir = Path(".pw-profile")
    user_data_dir.mkdir(exist_ok=True)

    captured_reqs: List[Captured] = []
    console_logs: List[Dict[str, Any]] = []
    page_errors: List[str] = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            locale="en-GB",
            timezone_id="Europe/London",
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        page = context.new_page()

        # Kill the easiest automation signal.
        page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """
        )

        page.on("console", lambda msg: console_logs.append({
            "type": msg.type,
            "text": msg.text,
            "location": msg.location,
        }))
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        def on_request(req):
            rt = req.resource_type
            if rt in {"xhr", "fetch"}:
                captured_reqs.append(Captured(url=req.url, method=req.method, resource_type=rt))

        def on_response(resp):
            req = resp.request
            rt = req.resource_type
            if rt not in {"xhr", "fetch"}:
                return
            # Add status + content-type to the most recent matching request entry
            try:
                ct = resp.headers.get("content-type")
            except Exception:
                ct = None
            # find last matching URL+method (cheap + good enough)
            for i in range(len(captured_reqs) - 1, -1, -1):
                if captured_reqs[i].url == req.url and captured_reqs[i].method == req.method:
                    captured_reqs[i].status = resp.status
                    captured_reqs[i].content_type = ct
                    break

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"Opening: {ARC_URL}")
        page.goto(ARC_URL, wait_until="domcontentloaded")

        # Best-effort accept cookie banners (common reason embeds don't load).
        for label in ["Accept", "I agree", "Agree", "Allow all", "Accept all"]:
            try:
                btn = page.get_by_role("button", name=label)
                if btn.count() > 0:
                    btn.first.click(timeout=1500)
                    break
            except Exception:
                pass

        # Nudge lazy-loaders
        for i in range(seconds):
            time.sleep(1)
            if i in {2, 5, 8, 12, 16}:
                try:
                    page.mouse.wheel(0, 900)
                except Exception:
                    pass

        context.close()

    # De-dupe
    uniq = {}
    for c in captured_reqs:
        key = (c.method.upper(), c.url)
        # Keep the richest version (with status/ct)
        prev = uniq.get(key)
        if prev is None:
            uniq[key] = c
        else:
            if (prev.status is None and c.status is not None) or (prev.content_type is None and c.content_type is not None):
                uniq[key] = c

    uniq_list = list(uniq.values())

    # Rank likely endpoints
    ranked: List[Tuple[int, Captured]] = []
    for c in uniq_list:
        score = 0
        if LIKELY_KEYWORDS.search(c.url):
            score += 5
        if c.status and 200 <= c.status < 300:
            score += 2
        if c.content_type and "json" in c.content_type.lower():
            score += 3
        if c.method.upper() == "GET":
            score += 1
        ranked.append((score, c))
    ranked.sort(key=lambda t: t[0], reverse=True)

    out = {
        "source_url": ARC_URL,
        "unique_xhr_fetch": len(uniq_list),
        "ranked_candidates": [
            {"score": s, **c.to_json()} for s, c in ranked
        ],
        "all_xhr_fetch": [c.to_json() for c in uniq_list],
        "console": console_logs[-200:],  # last 200 lines
        "page_errors": page_errors,
        "note": "Pick an index from ranked_candidates to replay with `fetch`.",
    }

    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {len(uniq_list)} unique XHR/fetch request(s) to: {out_path}")


def fetch(inp: Path, pick: int, out_path: Path) -> None:
    data = json.loads(inp.read_text(encoding="utf-8"))
    ranked = data.get("ranked_candidates") or []
    if not ranked:
        raise RuntimeError("No ranked_candidates found. Your widget probably didn't make any XHR/fetch calls.")

    if pick < 0 or pick >= len(ranked):
        raise ValueError(f"--pick out of range (0..{len(ranked)-1})")

    chosen = ranked[pick]
    url = chosen["url"]
    method = chosen["method"].upper()
    print(f"Replaying [{pick}] {method} {url}")

    sess = requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    })

    if method == "GET":
        r = sess.get(url, timeout=30)
    else:
        # If it's POST in ranked list, you likely need a body. We'll still try empty body.
        r = sess.request(method, url, timeout=30)

    print(f"HTTP {r.status_code} ({len(r.content)} bytes)")
    try:
        payload = r.json()
    except Exception:
        payload = {"raw_text": r.text[:20000]}

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote: {out_path}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("sniff")
    s1.add_argument("--out", required=True, type=Path)
    s1.add_argument("--seconds", type=int, default=20)

    s2 = sub.add_parser("fetch")
    s2.add_argument("--in", dest="inp", required=True, type=Path)
    s2.add_argument("--pick", required=True, type=int)
    s2.add_argument("--out", required=True, type=Path)

    args = ap.parse_args()

    if args.cmd == "sniff":
        sniff(args.out, seconds=args.seconds)
    else:
        fetch(args.inp, args.pick, args.out)


if __name__ == "__main__":
    main()
