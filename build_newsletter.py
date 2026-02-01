#!/usr/bin/env python3
"""
Claude-powered newsletter builder.

This script uses Claude SDK to orchestrate the full newsletter workflow:
- Gathering candidates from Perplexity + venue scraping
- Drafting newsletter in house style
- Critiquing and revising iteratively
- Publishing to Notion

Usage:
    python build_newsletter.py                  # Full workflow (gather + draft)
    python build_newsletter.py --draft-only     # Draft from latest candidates
    python build_newsletter.py --draft-only --run-id 20260119_120000  # Draft from specific run
    python build_newsletter.py --gather-only    # Only gather candidates
"""

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables (override=True to ensure fresh .env values)
load_dotenv(override=True)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.agents.claude_orchestrator import NewsletterOrchestrator


def main():
    parser = argparse.ArgumentParser(
        description="Build London Sauna Newsletter using Claude SDK"
    )

    parser.add_argument(
        "--mode",
        choices=["full", "draft-only", "gather-only"],
        default="full",
        help="Workflow mode: full (gather + draft), draft-only, or gather-only"
    )

    parser.add_argument(
        "--draft-only",
        action="store_true",
        help="Shortcut for --mode draft-only"
    )

    parser.add_argument(
        "--gather-only",
        action="store_true",
        help="Shortcut for --mode gather-only"
    )

    parser.add_argument(
        "--run-id",
        default="latest",
        help="Run ID to use for drafting (default: latest)"
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum draft revision iterations (default: 3)"
    )

    args = parser.parse_args()

    # Handle shortcuts
    if args.draft_only:
        args.mode = "draft-only"
    elif args.gather_only:
        args.mode = "gather-only"

    print()
    print("=" * 70)
    print("LONDON SAUNA NEWSLETTER BUILDER")
    print("Powered by Claude SDK")
    print("=" * 70)
    print()
    print(f"Mode: {args.mode}")
    if args.mode == "draft-only":
        print(f"Run ID: {args.run_id}")
    print(f"Max iterations: {args.max_iterations}")
    print()

    # Create orchestrator
    orchestrator = NewsletterOrchestrator()

    # Run workflow
    try:
        result = orchestrator.run(
            mode=args.mode,
            run_id=args.run_id,
            max_iterations=args.max_iterations
        )

        # Print results
        print()
        print("=" * 70)
        print("RESULT")
        print("=" * 70)
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Iterations: {result.get('iterations', 0)}")

        if result.get("final_message"):
            print()
            print(result["final_message"])

        print()

        # Exit code
        if result.get("status") == "success":
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user.")
        sys.exit(130)

    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
