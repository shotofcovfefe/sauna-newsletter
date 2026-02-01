#!/usr/bin/env python3
"""
Scrape Rebase class schedule via Mindbody widget endpoint.

This endpoint returns JavaScript (JSONP-ish). The cb(...) argument is often an
object where quotes are escaped (e.g. {\"class_sessions\":\"\\u003cdiv...\"}),
so we:
  1) unwrap cb(...)
  2) unescape once (unicode_escape)
  3) json.loads
  4) read markup from known keys (incl. class_sessions)

Then we do a minimal parse from the returned markup to produce instances.
"""

from __future__ import annotations

import argparse
import codecs
import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup


WIDGET_SCHEDULE_ID = 211646
BASE = "https://widgets.mindbodyonline.com"
LOAD_MARKUP = f"{BASE}/widgets/schedules/{WIDGET_SCHEDULE_ID}/load_markup"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

CALLBACK_WRAPPER_RE = re.compile(r"^[^(]+\((.*)\)\s*;?\s*$", re.DOTALL)

# Keys Mindbody widgets commonly use for markup chunks
MARKUP_KEYS = (
    "markup",
    "html",
    "content",
    "body",
    "response",
    "class_sessions",   # <-- the one your response uses
    "sessions",
)

URL_RE = re.compile(r"https?://[^\s\"'>]+")


@dataclass
class ClassInstance:
    title: str
    start: str
    end: Optional[str]
    instructor: Optional[str]
    location: Optional[str]
    signup_url: Optional[str]
    source_date: str
    source_url: str


def http_get(session: requests.Session, url: str) -> requests.Response:
    r = session.get(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Referer": "https://www.rebaserecovery.com/",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r


def _unicode_unescape_once(s: str) -> str:
    """
    Turn sequences like \\u003c into <, and \\\" into ".
    This matches the encoding style visible in your error preview.
    """
    return codecs.decode(s, "unicode_escape")


def _extract_cb_arg(js: str) -> str:
    js = js.strip()
    m = CALLBACK_WRAPPER_RE.match(js)
    return m.group(1).strip() if m else js


def _parse_js_object_payload(js_inner: str) -> Any:
    """
    The cb(...) argument is *sometimes* valid JSON; often it is a JSON-like string
    with escaped quotes. We try both.
    """
    # First try direct JSON
    try:
        return json.loads(js_inner)
    except Exception:
        pass

    # If it contains lots of \" or \uXXXX, unescape once then try JSON again.
    try:
        unescaped = _unicode_unescape_once(js_inner)
        return json.loads(unescaped)
    except Exception:
        pass

    # Some responses wrap a JSON string: cb("...") where ... is escaped JSON.
    # If so, unescape then try to parse the resulting string as JSON.
    if (js_inner.startswith('"') and js_inner.endswith('"')) or (js_inner.startswith("'") and js_inner.endswith("'")):
        try:
            # strip quotes, unescape, parse
            inner_str = js_inner[1:-1]
            inner_unescaped = _unicode_unescape_once(inner_str)
            return json.loads(inner_unescaped)
        except Exception:
            pass

    preview = js_inner[:800].replace("\n", "\\n")
    raise RuntimeError(f"Could not parse JS payload as JSON. First 800 chars: {preview}")


def fetch_markup(session: requests.Session, start_day: date) -> str:
    params = {
        "callback": "cb",
        "options[start_date]": start_day.isoformat(),
        "_": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
    }
    url = f"{LOAD_MARKUP}?{urlencode(params)}"
    r = http_get(session, url)

    js = r.text
    js_inner = _extract_cb_arg(js)

    payload = _parse_js_object_payload(js_inner)

    # payload might be a dict containing the markup
    if isinstance(payload, dict):
        for k in MARKUP_KEYS:
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v

        # Sometimes nested once
        for v in payload.values():
            if isinstance(v, dict):
                for k in MARKUP_KEYS:
                    vv = v.get(k)
                    if isinstance(vv, str) and vv.strip():
                        return vv

    # Rare case: payload is directly a string of markup
    if isinstance(payload, str) and payload.strip():
        return payload

    raise RuntimeError(f"Could not find markup in payload. Keys: {list(payload.keys()) if isinstance(payload, dict) else type(payload)}")


def discover_deeper_urls(markup_html: str) -> List[str]:
    urls = set()
    for m in URL_RE.finditer(markup_html):
        u = m.group(0)
        if any(k in u.lower() for k in ("mindbody", "healcode", "api", "class", "schedule", "booking", "appointment")):
            urls.add(u)
    return sorted(urls)


def parse_instances_from_markup(markup_html: str, source_day: date, source_url: str) -> List[ClassInstance]:
    """
    Minimal, but for Mindbody markup we can get very clean fields from data attributes:
      <div class="bw-session" ... data-bw-widget-mbo-class-id="21582" data-bw-widget-mbo-class-name="member_s_suite" ...>
    and there is usually a visible time element inside.
    """
    soup = BeautifulSoup(markup_html, "html.parser")

    instances: List[ClassInstance] = []

    # Mindbody widgets usually include sessions as div.bw-session
    for sess in soup.select(".bw-session"):
        # Skip empty day placeholders
        classes = sess.get("class") or []
        if "bw-session--empty" in classes:
            continue

        title = (
            sess.get("data-bw-widget-mbo-class-name")
            or sess.get("data-bw-widget-class-name")
            or sess.get("data-bw-widget-title")
        )

        # Find a visible time if present
        # Common: .bw-session__time or similar
        time_el = sess.select_one(".bw-session__time") or sess.find(string=re.compile(r"\b\d{1,2}:\d{2}\s*(AM|PM)\b", re.I))
        start = ""
        if time_el:
            start = time_el.get_text(" ", strip=True) if hasattr(time_el, "get_text") else str(time_el).strip()

        # Signup link if present
        signup_url = None
        a = sess.find("a", href=True)
        if a:
            href = a["href"]
            signup_url = f"{BASE}{href}" if href.startswith("/") else href

        # If we couldn't find title from attributes, try visible heading
        if not title:
            t = sess.find(["strong", "b", "h3", "h4", "h5"])
            if t:
                title = t.get_text(" ", strip=True)
        if not title:
            title = "unknown"

        instances.append(
            ClassInstance(
                title=title,
                start=start,
                end=None,
                instructor=None,
                location=None,
                signup_url=signup_url,
                source_date=source_day.isoformat(),
                source_url=source_url,
            )
        )

    # Dedup by (title, start, signup_url)
    seen = set()
    uniq: List[ClassInstance] = []
    for x in instances:
        key = (x.title, x.start, x.signup_url)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(x)

    return uniq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=str, default=None, help="YYYY-MM-DD (defaults to today)")
    ap.add_argument("--days", type=int, default=14, help="How many days to scrape starting from --start")
    ap.add_argument("--out", required=True, help="Output JSON file")
    ap.add_argument(
        "--dump-markup-dir",
        type=str,
        default=None,
        help="Optional directory to save raw markup per day for debugging",
    )
    args = ap.parse_args()

    start_day = date.fromisoformat(args.start) if args.start else date.today()
    end_day = start_day + timedelta(days=max(args.days - 1, 0))

    session = requests.Session()

    all_instances: List[ClassInstance] = []
    all_discovered_urls: List[str] = []
    errors: List[Dict[str, Any]] = []

    d = start_day
    while d <= end_day:
        try:
            # Stable source url (no cachebuster) for traceability
            source_url = f"{LOAD_MARKUP}?{urlencode({'callback': 'cb', 'options[start_date]': d.isoformat()})}"

            markup = fetch_markup(session, d)

            if args.dump_markup_dir:
                os.makedirs(args.dump_markup_dir, exist_ok=True)
                with open(os.path.join(args.dump_markup_dir, f"{d.isoformat()}.html"), "w", encoding="utf-8") as f:
                    f.write(markup)

            all_discovered_urls.extend(discover_deeper_urls(markup))
            all_instances.extend(parse_instances_from_markup(markup, d, source_url))

        except Exception as e:
            errors.append({"date": d.isoformat(), "error": str(e)})

        d += timedelta(days=1)

    all_discovered_urls = sorted(set(all_discovered_urls))

    payload = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "widget_schedule_id": WIDGET_SCHEDULE_ID,
        "date_range": {"start": start_day.isoformat(), "end": end_day.isoformat()},
        "instance_count": len(all_instances),
        "instances": [asdict(x) for x in all_instances],
        "discovered_urls_in_markup": all_discovered_urls,
        "errors": errors,
        "note": (
            "Uses Mindbody widget load_markup and extracts markup from JS callback payload (handles escaped JSON). "
            "If discovered_urls_in_markup includes a real JSON endpoint, prefer that and stop parsing markup."
        ),
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote {args.out} (instances={len(all_instances)}, errors={len(errors)})")


if __name__ == "__main__":
    main()
