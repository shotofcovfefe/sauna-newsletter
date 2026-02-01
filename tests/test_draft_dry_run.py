#!/usr/bin/env python3
"""
Dry-run test for draft workflow using Claude SDK orchestrator.
Tests that all components can be loaded without errors before expensive Claude API calls.
"""

import sys
import os
from pathlib import Path

def test_draft_workflow_dry_run(run_id: str):
    """Test that the draft workflow can load data and initialize without errors."""

    print("=" * 60)
    print("DRY RUN TEST - Draft Workflow (Claude SDK)")
    print("=" * 60)
    print()

    # Test 1: Check candidates file exists
    print("[1/7] Checking candidates file...")
    candidates_file = Path(f"data/runs/{run_id}_candidates.json")
    if not candidates_file.exists():
        print(f"❌ FAIL: {candidates_file} not found")
        return False
    print(f"✓ Found: {candidates_file}")
    print()

    # Test 2: Load and parse JSON
    print("[2/7] Loading JSON data...")
    import json
    try:
        with open(candidates_file, "r") as f:
            data = json.load(f)
        print(f"✓ Loaded JSON with keys: {list(data.keys())}")
    except Exception as e:
        print(f"❌ FAIL: Could not load JSON: {e}")
        return False
    print()

    # Test 3: Parse candidates
    print("[3/7] Parsing candidates...")
    from src.models.types import Candidate
    try:
        candidates = [Candidate(**c) for c in data["candidates"]]
        print(f"✓ Parsed {len(candidates)} candidates")
    except Exception as e:
        print(f"❌ FAIL: Could not parse candidates: {e}")
        return False
    print()

    # Test 4: Check spotlight data
    print("[4/7] Checking spotlight data...")
    if data.get("spotlight_venue"):
        print(f"✓ Spotlight venue: {data['spotlight_venue']}")
        if data.get("spotlight_research"):
            print(f"✓ Spotlight research: {len(data['spotlight_research'])} queries")
        else:
            print("⚠ Warning: No spotlight research found")
    else:
        print("⚠ Warning: No spotlight venue found")
    print()

    # Test 5: Test Claude orchestrator import
    print("[5/7] Testing Claude orchestrator import...")
    try:
        from src.agents.claude_orchestrator import NewsletterOrchestrator
        print("✓ NewsletterOrchestrator imported successfully")
    except Exception as e:
        print(f"❌ FAIL: Could not import NewsletterOrchestrator: {e}")
        return False
    print()

    # Test 6: Test tool functions import
    print("[6/7] Testing draft tool functions...")
    try:
        from src.tools.draft_tools import (
            draft_newsletter_content,
            critique_newsletter,
            revise_newsletter_content
        )
        print("✓ Draft tool functions imported successfully")
    except Exception as e:
        print(f"❌ FAIL: Could not import draft tools: {e}")
        return False
    print()

    # Test 7: Check ANTHROPIC_API_KEY
    print("[7/7] Checking environment variables...")
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ FAIL: ANTHROPIC_API_KEY not set")
        print("  Set this in your .env file")
        return False
    print("✓ ANTHROPIC_API_KEY is set")
    print()

    print("=" * 60)
    print("✅ ALL DRY RUN TESTS PASSED")
    print("=" * 60)
    print()
    print("Safe to run: python draft.py --run-id", run_id)
    print()
    print("NOTE: This will use Claude Opus 4 via the agentic orchestrator.")
    print("Claude will autonomously:")
    print("  1. Load candidates from", run_id)
    print("  2. Select best candidates")
    print("  3. Load previous issues")
    print("  4. Draft newsletter (with spotlight data)")
    print("  5. Critique and revise")
    print("  6. Publish to Notion")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_draft_dry_run.py <run_id>")
        print("Example: python test_draft_dry_run.py 20260127_214331")
        sys.exit(1)

    run_id = sys.argv[1]
    success = test_draft_workflow_dry_run(run_id)
    sys.exit(0 if success else 1)
