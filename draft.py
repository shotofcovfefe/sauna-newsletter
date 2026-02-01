#!/usr/bin/env python3
"""
Draft workflow: Load candidates and draft newsletter using Claude SDK orchestrator.

Usage:
    python draft.py --run-id 20260111_153045       # Draft from specific run
    python draft.py --run-id latest                # Use latest gather run
    python draft.py --list                         # List available runs
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.claude_orchestrator import NewsletterOrchestrator
from pathlib import Path


def list_available_runs():
    """List available candidate runs."""
    runs_dir = Path("data/runs")
    if not runs_dir.exists():
        return []

    run_files = list(runs_dir.glob("*_candidates.json"))
    run_ids = [f.stem.replace("_candidates", "") for f in run_files]

    return sorted(run_ids, reverse=True)


def main():
    """Main entry point for draft workflow."""
    parser = argparse.ArgumentParser(
        description="Draft and publish newsletter from candidates using Claude SDK"
    )
    parser.add_argument(
        "--run-id",
        help="Run ID from gather workflow (or 'latest' for most recent)",
        default=None
    )
    parser.add_argument(
        "--list",
        help="List available runs",
        action="store_true"
    )
    parser.add_argument(
        "--max-iterations",
        help="Maximum drafting iterations",
        type=int,
        default=3
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Handle --list
    if args.list:
        print("Available runs:")
        runs = list_available_runs()
        if not runs:
            print("  (none found)")
        else:
            for run_id in runs:
                print(f"  - {run_id}")
        sys.exit(0)

    # Determine run_id
    run_id = args.run_id

    if not run_id or run_id == "latest":
        runs = list_available_runs()
        if not runs:
            print("ERROR: No candidate runs found. Run gather.py first.")
            sys.exit(1)
        run_id = runs[0]
        print(f"Using latest run: {run_id}\n")

    # Verify required env vars
    required_vars = ["ANTHROPIC_API_KEY", "NOTION_API_KEY", "NOTION_DRAFT_NEWSLETTERS_DB_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these in your .env file")
        sys.exit(1)

    # Run Claude orchestrator in draft-only mode
    try:
        orchestrator = NewsletterOrchestrator()
        result = orchestrator.run(
            mode="draft-only",
            run_id=run_id,
            max_iterations=args.max_iterations
        )

        print(f"\n✓ Draft workflow complete!")
        print(f"\nStatus: {result.get('status')}")
        print(f"Iterations: {result.get('iterations')}")

        if result.get('final_message'):
            print(f"\n{result['final_message']}")

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
