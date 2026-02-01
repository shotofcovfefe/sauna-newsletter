#!/usr/bin/env python3
"""
Cleanup script to delete bad email records created with faulty LLM integration.

This script identifies and deletes:
1. Email artifacts with confidence_score = 0.3 and summary containing "(classification failed)"
2. Associated email records

Usage:
    python src/scripts/cleanup_bad_emails.py              # Dry run (shows what would be deleted)
    python src/scripts/cleanup_bad_emails.py --execute    # Actually delete the records
"""

import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def main():
    """Clean up bad email records."""
    parser = argparse.ArgumentParser(
        description="Cleanup bad email records from failed LLM integration"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete records (default is dry run)"
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Verify required env vars
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("ERROR: Missing SUPABASE_URL or SUPABASE_KEY")
        sys.exit(1)

    # Initialize Supabase
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY")
    )

    print("=" * 60)
    print("Email Cleanup Script")
    print("=" * 60)
    print()

    # Find bad artifacts (confidence 0.3 with classification failed)
    print("Searching for bad artifacts...")
    try:
        bad_artifacts = (
            supabase.table("email_artifacts")
            .select("id, email_id, summary, confidence_score")
            .eq("confidence_score", 0.3)
            .ilike("summary", "%classification failed%")
            .execute()
        )

        count = len(bad_artifacts.data or [])
        print(f"Found {count} bad artifacts with confidence=0.3 and failed classification")
        print()

        if count == 0:
            print("No bad records to clean up.")
            return

        # Show sample
        print("Sample of bad records:")
        for artifact in (bad_artifacts.data or [])[:5]:
            print(f"  - Artifact ID: {artifact['id']}")
            print(f"    Email ID: {artifact['email_id']}")
            print(f"    Summary: {artifact['summary']}")
            print(f"    Confidence: {artifact['confidence_score']}")
            print()

        if not args.execute:
            print("=" * 60)
            print("DRY RUN MODE (no changes made)")
            print("=" * 60)
            print()
            print("To actually delete these records, run:")
            print("  python src/scripts/cleanup_bad_emails.py --execute")
            print()
            print(f"This would delete:")
            print(f"  - {count} email artifacts")
            print(f"  - {count} corresponding emails")
            return

        # Execute deletion
        print("=" * 60)
        print("EXECUTING DELETION")
        print("=" * 60)
        print()

        deleted_artifacts = 0
        deleted_emails = 0
        email_ids = set()

        for artifact in bad_artifacts.data or []:
            artifact_id = artifact['id']
            email_id = artifact['email_id']
            email_ids.add(email_id)

            # Delete artifact
            try:
                supabase.table("email_artifacts").delete().eq("id", artifact_id).execute()
                deleted_artifacts += 1
                print(f"✓ Deleted artifact: {artifact_id}")
            except Exception as e:
                print(f"✗ Failed to delete artifact {artifact_id}: {e}")

        # Delete associated emails
        for email_id in email_ids:
            try:
                supabase.table("emails").delete().eq("id", email_id).execute()
                deleted_emails += 1
                print(f"✓ Deleted email: {email_id}")
            except Exception as e:
                print(f"✗ Failed to delete email {email_id}: {e}")

        print()
        print("=" * 60)
        print("Cleanup Complete")
        print("=" * 60)
        print(f"Deleted {deleted_artifacts} artifacts")
        print(f"Deleted {deleted_emails} emails")
        print()

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
