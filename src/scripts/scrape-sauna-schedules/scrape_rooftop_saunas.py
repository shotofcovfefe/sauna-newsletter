#!/usr/bin/env python3
"""
Sniff JSON/XHR endpoints used by RooftopSaunas booking flow, then optionally replay.
- No HTML parsing required.
- Uses Playwright to click into booking and records XHR/fetch JSON responses.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, Page, Response


JSON_CT_RE = re.compile(r"application/(json|problem\+json)|text/json", re.I)

KEYWORDS = (
    "availability", "availabilities", "timeslot", "time_slot", "slots",
    "schedule", "booking", "appointments", "appointment", "checkout",
    "session", "sessions", "inventory"
)

@dataclass(frozen=True)
class Captured:
    url: str
    method: str
    status: int
    content_type: str
    resource_type: str

def is_interesting(resp: Response) -> bool:
    try:
        req = resp.request
        url = resp.url
        ct = (resp.headers.get("content-type") or "").lower()
        if resp.status < 200 or resp.status >= 400:
            return False
        if req.resource_type not in ("xhr", "fetch"):
            return False
        if not JSON_CT_RE.search(ct):
            return False

        # Filter out obvious analytics noise
        host = urlparse(url).netloc.lower()
        if any(x in host for x in ("google-analytics", "googletagmanager", "hotjar", "doubleclick", "stripe.com")):
            return False

        # Prefer “booking-ish” URLs
        u = url.lower()
        if any(k in u for k in KEYWORDS):
            return True

        # Still allow JSON endpoints if they are first-party or plausible booking hosts
        if any(x in host for x in ("rooftopsaunas", "squareup", "square.site", "squarecdn", "appointments", "book", "booking")):
            return True

        return False
    except Exception:
        return False

def click_booking_entrypoints(page: Page) -> None:
    """
    Try a few common entrypoints. Non-fatal if not found.
    """
    candidates = [
        "text=Book a Session",
        "text=Book a session",
        "text=Book now",
        "text=Book",
        "a:has-text('Book a Session')",
        "a:has-text('Book a session')",
        "button:has-text('Book a Session')",
        "button:has-text('Book')",
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=2000)
                return
        except Exception:
            continue

def sniff(url: str, out: str, headless: bool = True, timeout_ms: int = 30000) -> Dict[str, Any]:
    captured: List[Captured] = []
    seen: Set[Tuple[str, str]] = set()

    def on_response(resp: Response) -> None:
        if not is_interesting(resp):
            return
        req = resp.request
        key = (req.method, resp.url)
        if key in seen:
            return
        seen.add(key)
        captured.append(
            Captured(
                url=resp.url,
                method=req.method,
                status=resp.status,
                content_type=(resp.headers.get("content-type") or ""),
                resource_type=req.resource_type,
            )
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.on("response", on_response)

        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        # Try to enter booking flow (may open a new tab/window)
        click_booking_entrypoints(page)

        # If it opened a popup, attach to it and wait there too.
        # (Playwright exposes popups via page.expect_popup, but this is “best effort”.)
        page.wait_for_timeout(4000)

        # Also wait for network to settle after clicks/redirects
        try:
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass

        browser.close()

    # Rank candidates (very rough)
    ranked = sorted(
        (asdict(c) for c in captured),
        key=lambda r: (
            sum(1 for k in KEYWORDS if k in r["url"].lower()),
            1 if "application/json" in (r["content_type"] or "").lower() else 0,
        ),
        reverse=True,
    )

    payload = {
        "source_url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "unique_xhr_fetch_json": len(ranked),
        "ranked_candidates": ranked,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload

def replay(candidate_url: str, out: str) -> None:
    """
    Basic replay using requests-like fetch via Playwright (keeps headers/cookies simple).
    Useful if endpoint needs browser-ish headers.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        resp = page.request.get(candidate_url)
        data = {"status": resp.status, "headers": dict(resp.headers), "url": candidate_url}
        try:
            body = resp.json()
            data["json"] = body
        except Exception:
            data["text"] = resp.text()

        browser.close()

    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("sniff", help="Sniff booking JSON endpoints")
    s1.add_argument("--url", required=True)
    s1.add_argument("--out", required=True)
    s1.add_argument("--headed", action="store_true", help="Run non-headless for debugging")
    s1.add_argument("--timeout-ms", type=int, default=30000)

    s2 = sub.add_parser("replay", help="Replay one candidate URL and dump JSON")
    s2.add_argument("--candidate-url", required=True)
    s2.add_argument("--out", required=True)

    args = ap.parse_args()

    if args.cmd == "sniff":
        sniff(args.url, args.out, headless=not args.headed, timeout_ms=args.timeout_ms)
        print(f"Wrote sniff results: {args.out}")
    elif args.cmd == "replay":
        replay(args.candidate_url, args.out)
        print(f"Wrote replay response: {args.out}")

if __name__ == "__main__":
    main()
