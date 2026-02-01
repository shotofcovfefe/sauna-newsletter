#!/usr/bin/env python3
"""
Main entry point for the London Sauna Newsletter Drafting System.

Note: The gather workflow has been removed. Use the standalone scripts instead:
- /scrape-all  - Scrape venue events
- /scrape-news - Scrape sauna news via Perplexity

This script now only runs the DRAFT workflow:
- Load candidates → draft → publish to Notion

Usage:
    python main.py                      # Run draft workflow with latest run
    python main.py --run-id 20260119    # Run draft with specific run ID
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.workflows.draft_workflow import run_draft_workflow, list_available_runs


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run London Sauna Newsletter draft workflow"
    )
    parser.add_argument(
        "--run-id",
        help="Run ID for draft workflow",
        default=None
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Verify required env vars
    required_vars = [
        "GEMINI_API_KEY",
        "NOTION_API_KEY",
        "NOTION_DRAFT_NEWSLETTERS_DB_ID"
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these in your .env file")
        sys.exit(1)

    try:
        # Determine run_id
        run_id = args.run_id
        if not run_id:
            # Use latest
            runs = list_available_runs()
            if not runs:
                print("ERROR: No candidate runs found.")
                print("\nPlease run the scraping workflows first:")
                print("  /scrape-all  - Scrape venue events")
                print("  /scrape-news - Scrape sauna news")
                sys.exit(1)
            run_id = runs[0]
            print(f"Using latest run: {run_id}\n")

        # Run draft workflow
        print("=" * 60)
        print("DRAFT WORKFLOW")
        print("=" * 60)
        print()

        draft_state = run_draft_workflow(
            run_id=run_id,
            max_iterations=3,
            previous_issues_limit=5
        )

        notion_page_id = draft_state.get('notion_page_id')

        # Summary
        print()
        print("=" * 60)
        print("DRAFT WORKFLOW COMPLETE")
        print("=" * 60)
        print(f"Run ID: {run_id}")
        print(f"Notion page: {notion_page_id}")
        print()

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
