#!/usr/bin/env python3
"""
Unified sauna schedule scraper and aggregator.

This script orchestrates all individual venue scrapers, normalizes their outputs,
deduplicates events, and produces a single unified dataset.

Usage:
    python src/scripts/aggregate_sauna_schedules.py --days 7 --out data/scraped/combined.json
    python src/scripts/aggregate_sauna_schedules.py --skip-scrapers rooftop_saunas,arc_momence
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

from src.models.scraped_event import ScrapedEvent
from src.services.scraper_normalizers import load_and_normalize
from src.utils.event_filters import filter_newsletter_events, print_filter_stats


# Scraper configurations
SCRAPERS = {
    "arc_marianatek": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_arc_marianatek.py",
        "cmd_template": [
            "python", "{script}",
            "--days", "{days}",
            "--out-json", "{output}"
        ],
        "output_file": "arc_classes.json",
        "enabled": True,
        "timeout": 60,
    },
    "community_sauna_legitfit": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_community_sauna_legitfit.py",
        "cmd_template": [
            "python", "{script}",
            "--days", "{days}",
            "--out", "{output}"
        ],
        "output_file": "community_sauna.json",
        "enabled": True,
        "timeout": 120,
    },
    "rebase_mindbody": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_rebase_mindbody.py",
        "cmd_template": [
            "python", "{script}",
            "--days", "{days}",
            "--out", "{output}"
        ],
        "output_file": "rebase_classes.json",
        "enabled": True,
        "timeout": 90,
    },
    "momence_schedule": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_momence_schedule_sauna_and_plunge.py",
        "cmd_template": [
            "python", "{script}",
            "--host-id", "99521",
            "--from-date", "{from_date}",
            "--page-size", "200",
            "--out", "{output}"
        ],
        "output_file": "sauna_plunge.json",
        "enabled": True,
        "timeout": 60,
    },
    # Playwright-based scrapers - more complex, may need manual intervention
    "arc_momence": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_arc_momence.py",
        "cmd_template": [
            "python", "{script}", "sniff",
            "--out", "{output}",
            "--seconds", "20"
        ],
        "output_file": "arc_momence_discovered.json",
        "enabled": False,  # Requires Playwright + manual workflow
        "timeout": 120,
    },
    "rooftop_saunas": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_rooftop_saunas.py",
        "cmd_template": [
            "python", "{script}", "sniff",
            "--url", "https://www.rooftopsaunas.com/",
            "--out", "{output}"
        ],
        "output_file": "rooftop_saunas_discovered.json",
        "enabled": False,  # Requires Playwright + manual workflow
        "timeout": 120,
    },
    "swesauna": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_swesauna.py",
        "cmd_template": [
            "python", "{script}",
            "--out", "{output}"
        ],
        "output_file": "swesauna_events.json",
        "enabled": True,
        "timeout": 90,
    },
    "sauna_social_club": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_sauna_social_club.py",
        "cmd_template": [
            "python", "{script}",
            "--out", "{output}"
        ],
        "output_file": "sauna_social_club_events.json",
        "enabled": True,
        "timeout": 60,
    },
    "wellnest_eventbrite": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_wellnest_eventbrite.py",
        "cmd_template": [
            "python", "{script}",
            "--out", "{output}"
        ],
        "output_file": "wellnest_events.json",
        "enabled": True,
        "timeout": 60,
    },
    "urban_heat_momence": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_urban_heat_momence.py",
        "cmd_template": [
            "python", "{script}",
            "--out", "{output}"
        ],
        "output_file": "urban_heat_events.json",
        "enabled": True,
        "timeout": 60,
    },
    "andsoul_momence": {
        "script": "src/scripts/scrape-sauna-schedules/scrape_andsoul_momence.py",
        "cmd_template": [
            "python", "{script}",
            "--host-id", "47026",
            "--days", "{days}",
            "--out", "{output}"
        ],
        "output_file": "andsoul_events.json",
        "enabled": True,
        "timeout": 60,
    },
}


def get_date_range(days: int) -> tuple[date, date]:
    """Get start and end dates for scraping."""
    start = date.today()
    end = start + timedelta(days=days - 1)
    return start, end


def get_from_date_iso(days: int) -> str:
    """Get ISO format date for Momence API (requires timezone)."""
    now = datetime.now(timezone.utc)
    # Format: 2026-01-14T21:30:00.000Z
    return now.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def run_scraper(
    scraper_name: str,
    config: Dict[str, Any],
    days: int,
    temp_dir: Path,
) -> Dict[str, Any]:
    """
    Run a single scraper and return its result metadata.

    Returns:
        Dict with keys: scraper, success, output_file, error, event_count
    """
    result = {
        "scraper": scraper_name,
        "success": False,
        "output_file": None,
        "output_file_str": None,
        "error": None,
        "event_count": 0,
    }

    if not config.get("enabled", False):
        result["error"] = "Disabled"
        return result

    # Prepare output file
    output_file = temp_dir / config["output_file"]

    # Build command
    cmd = []
    for part in config["cmd_template"]:
        cmd.append(
            part.format(
                script=config["script"],
                days=days,
                output=str(output_file),
                from_date=get_from_date_iso(days),
            )
        )

    print(f"[{scraper_name}] Running: {' '.join(cmd)}")

    try:
        # Get current environment (includes vars from .env via load_dotenv)
        env = os.environ.copy()

        # Run scraper with timeout
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.get("timeout", 120),
            cwd=Path.cwd(),
            env=env,
        )

        if proc.returncode == 0:
            result["success"] = True
            result["output_file"] = output_file
            result["output_file_str"] = str(output_file)
            print(f"[{scraper_name}] ✓ Success")
        else:
            result["error"] = f"Exit code {proc.returncode}: {proc.stderr[:200]}"
            print(f"[{scraper_name}] ✗ Failed: {result['error']}")

    except subprocess.TimeoutExpired:
        result["error"] = f"Timeout after {config.get('timeout')}s"
        print(f"[{scraper_name}] ✗ Timeout")
    except Exception as e:
        result["error"] = str(e)
        print(f"[{scraper_name}] ✗ Error: {e}")

    return result


def deduplicate_events(events: List[ScrapedEvent]) -> List[ScrapedEvent]:
    """
    Deduplicate events based on venue, time, and name.

    Strategy: Keep the event with the most complete information.
    """
    seen: Dict[tuple, ScrapedEvent] = {}

    for event in events:
        key = event.dedup_key()

        if key not in seen:
            seen[key] = event
        else:
            # Keep the one with more non-None fields
            existing = seen[key]
            existing_score = sum(1 for v in existing.model_dump().values() if v is not None)
            new_score = sum(1 for v in event.model_dump().values() if v is not None)

            if new_score > existing_score:
                seen[key] = event

    return list(seen.values())


def aggregate_all_scrapers(
    days: int,
    skip_scrapers: Optional[Set[str]] = None,
    parallel: bool = True,
    max_workers: int = 4,
) -> Dict[str, Any]:
    """
    Run all enabled scrapers and aggregate results.

    Returns:
        Dict with aggregated data and metadata
    """
    skip_scrapers = skip_scrapers or set()

    # Create temp directory for scraper outputs
    temp_dir = Path("data/scraped/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Filter enabled scrapers
    active_scrapers = {
        name: config
        for name, config in SCRAPERS.items()
        if name not in skip_scrapers and config.get("enabled", False)
    }

    print(f"\n{'='*70}")
    print(f"Running {len(active_scrapers)} scrapers for {days} days...")
    print(f"{'='*70}\n")

    # Run scrapers
    scraper_results = []

    if parallel and len(active_scrapers) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_scraper, name, config, days, temp_dir): name
                for name, config in active_scrapers.items()
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    scraper_results.append(result)
                except Exception as e:
                    scraper_name = futures[future]
                    scraper_results.append({
                        "scraper": scraper_name,
                        "success": False,
                        "error": str(e),
                        "event_count": 0,
                    })
    else:
        # Sequential execution
        for name, config in active_scrapers.items():
            result = run_scraper(name, config, days, temp_dir)
            scraper_results.append(result)

    # Normalize and aggregate events
    print(f"\n{'='*70}")
    print("Normalizing and aggregating events...")
    print(f"{'='*70}\n")

    all_events: List[ScrapedEvent] = []
    normalization_errors = []

    for result in scraper_results:
        if not result["success"]:
            continue

        scraper_name = result["scraper"]
        output_file = result["output_file"]

        try:
            events = load_and_normalize(output_file, scraper_name)
            all_events.extend(events)
            result["event_count"] = len(events)
            print(f"[{scraper_name}] Normalized {len(events)} events")
        except Exception as e:
            error_msg = f"Failed to normalize {scraper_name}: {e}"
            normalization_errors.append(error_msg)
            print(f"[{scraper_name}] ✗ Normalization error: {e}")

    # Deduplicate
    print(f"\nDeduplicating {len(all_events)} events...")
    deduplicated_events = deduplicate_events(all_events)
    print(f"After deduplication: {len(deduplicated_events)} unique events")

    # Sort by start datetime
    def sort_key(event: ScrapedEvent) -> str:
        return event.start_datetime or event.date or "9999-99-99"

    deduplicated_events.sort(key=sort_key)

    # Prepare summary (remove PosixPath objects for JSON serialization)
    serializable_results = []
    for r in scraper_results:
        result_copy = r.copy()
        # Remove PosixPath, keep string version
        if "output_file" in result_copy:
            del result_copy["output_file"]
        serializable_results.append(result_copy)

    summary = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "date_range": {
            "start": date.today().isoformat(),
            "end": (date.today() + timedelta(days=days - 1)).isoformat(),
            "days": days,
        },
        "scrapers": {
            "total": len(active_scrapers),
            "successful": sum(1 for r in scraper_results if r["success"]),
            "failed": sum(1 for r in scraper_results if not r["success"]),
            "results": serializable_results,
        },
        "events": {
            "total_raw": len(all_events),
            "total_deduplicated": len(deduplicated_events),
            "duplicates_removed": len(all_events) - len(deduplicated_events),
            "by_venue": {},
        },
        "errors": normalization_errors,
    }

    # Count by venue
    for event in deduplicated_events:
        venue = event.venue
        summary["events"]["by_venue"][venue] = summary["events"]["by_venue"].get(venue, 0) + 1

    return {
        "summary": summary,
        "events": [event.model_dump() for event in deduplicated_events],
    }


def print_summary(data: Dict[str, Any]) -> None:
    """Print a human-readable summary of the scraping results."""
    summary = data["summary"]
    scrapers = summary["scrapers"]
    events = summary["events"]

    print(f"\n{'='*70}")
    print("SCRAPING SUMMARY")
    print(f"{'='*70}")
    print(f"Date range: {summary['date_range']['start']} to {summary['date_range']['end']} ({summary['date_range']['days']} days)")
    print(f"Scraped at: {summary['scraped_at']}")
    print()
    print(f"Scrapers: {scrapers['successful']}/{scrapers['total']} successful")
    print()

    for result in scrapers["results"]:
        status = "✓" if result["success"] else "✗"
        count = f"({result['event_count']} events)" if result["success"] else f"({result['error']})"
        print(f"  {status} {result['scraper']:<30} {count}")

    print()
    print(f"Events:")
    print(f"  Total raw: {events['total_raw']}")
    print(f"  Duplicates removed: {events['duplicates_removed']}")
    print(f"  Unique events: {events['total_deduplicated']}")
    print()
    print(f"Events by venue:")
    for venue, count in sorted(events["by_venue"].items()):
        print(f"  {venue:<30} {count} events")

    if summary.get("errors"):
        print()
        print("Errors:")
        for error in summary["errors"]:
            print(f"  ✗ {error}")

    print(f"{'='*70}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate sauna schedules from all venue scrapers"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to scrape (default: 7)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON file (default: data/scraped/YYYYMMDD_HHMMSS_combined.json)",
    )
    parser.add_argument(
        "--skip-scrapers",
        type=str,
        default="",
        help="Comma-separated list of scrapers to skip (e.g., 'arc_momence,rooftop_saunas')",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run scrapers sequentially instead of in parallel",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum parallel workers (default: 4)",
    )
    parser.add_argument(
        "--filter-high-frequency",
        action="store_true",
        help="Filter out high-frequency standard sessions (for newsletter drafting)",
    )

    args = parser.parse_args()

    # Parse skip list
    skip_scrapers = set()
    if args.skip_scrapers:
        skip_scrapers = {s.strip() for s in args.skip_scrapers.split(",") if s.strip()}

    # Run aggregation
    try:
        data = aggregate_all_scrapers(
            days=args.days,
            skip_scrapers=skip_scrapers,
            parallel=not args.sequential,
            max_workers=args.max_workers,
        )
    except Exception as e:
        print(f"Error during aggregation: {e}", file=sys.stderr)
        return 1

    # Determine output file
    if args.out:
        output_file = args.out
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(f"data/scraped/{timestamp}_combined.json")

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Apply filtering if requested
    if args.filter_high_frequency:
        print("\n" + "="*70)
        print("Applying newsletter event filter (excluding high-frequency sessions)...")
        print("="*70)

        filter_result = filter_newsletter_events(data["events"])
        print_filter_stats(filter_result)

        # Update data with filtered events
        data["events"] = filter_result["included"]
        data["summary"]["events"]["total_filtered"] = len(filter_result["included"])
        data["summary"]["events"]["filtered_out"] = len(filter_result["excluded"])
        data["summary"]["filter_stats"] = filter_result["stats"]

    # Write output
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Print summary
    print_summary(data)

    if args.filter_high_frequency:
        print(f"\n✓ Newsletter-ready events: {len(data['events'])}")

    print(f"\nOutput written to: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
