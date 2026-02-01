#!/usr/bin/env python3
"""
Gather workflow: Collect newsletter candidates from all sources.

This script runs all data collection steps using a LangGraph workflow:
1. Load venue watchlist
2. Scrape venue events
3. Fetch email candidates from Supabase
4. Search for news via Perplexity
5. Deduplicate and extract candidates
6. Save to candidates file

Usage:
    python gather.py
    python gather.py --run-id 20260125_120000  # Custom run ID
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.workflows.gather_workflow import run_gather_workflow


def main():
    """Main entry point for gather workflow."""
    parser = argparse.ArgumentParser(
        description="Gather newsletter candidates from all sources"
    )
    parser.add_argument(
        "--run-id",
        help="Custom run ID (defaults to timestamp)",
        default=None
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Verify required env vars
    required_vars = ["GEMINI_API_KEY", "PERPLEXITY_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these in your .env file")
        sys.exit(1)

    # Optional: Warn about Supabase (emails will be skipped if not configured)
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("ℹ Note: Supabase not configured - email candidates will be skipped")
        print()

    # Run workflow
    try:
        final_state = run_gather_workflow(run_id=args.run_id)
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n\nGathering interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
