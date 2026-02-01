#!/usr/bin/env python3
"""
Nuclear option: Delete ALL emails and artifacts from database.

Use this when you want to completely reset and re-scrape from scratch.

Usage:
    python src/scripts/delete_all_emails.py              # Dry run (shows what would be deleted)
    python src/scripts/delete_all_emails.py --execute    # Actually delete everything
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
    """Delete all email records."""
    parser = argparse.ArgumentParser(
        description="Delete ALL emails and artifacts (nuclear option)"
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
    print("Delete All Emails - Nuclear Option")
    print("=" * 60)
    print()

    # Count emails
    try:
        emails = supabase.table("emails").select("id", count="exact").execute()
        email_count = emails.count if hasattr(emails, 'count') else len(emails.data or [])

        artifacts = supabase.table("email_artifacts").select("id", count="exact").execute()
        artifact_count = artifacts.count if hasattr(artifacts, 'count') else len(artifacts.data or [])

        newsletter_links = supabase.table("newsletter_artifacts").select("artifact_id", count="exact").execute()
        link_count = newsletter_links.count if hasattr(newsletter_links, 'count') else len(newsletter_links.data or [])

        print(f"Found {email_count} emails")
        print(f"Found {artifact_count} artifacts")
        print(f"Found {link_count} newsletter links")
        print()

        if email_count == 0 and artifact_count == 0:
            print("No records to delete.")
            return

        if not args.execute:
            print("=" * 60)
            print("DRY RUN MODE (no changes made)")
            print("=" * 60)
            print()
            print("To actually delete ALL records, run:")
            print("  python src/scripts/delete_all_emails.py --execute")
            print()
            print(f"This would delete:")
            print(f"  - {email_count} emails")
            print(f"  - {artifact_count} artifacts")
            print(f"  - {link_count} newsletter links")
            print()
            print("⚠️  WARNING: This cannot be undone!")
            return

        # Execute deletion
        print("=" * 60)
        print("EXECUTING DELETION")
        print("=" * 60)
        print()

        # Delete in correct order (foreign keys)

        # 1. Delete newsletter_artifacts (references email_artifacts)
        if link_count > 0:
            supabase.table("newsletter_artifacts").delete().neq("artifact_id", "00000000-0000-0000-0000-000000000000").execute()
            print(f"✓ Deleted {link_count} newsletter links")

        # 2. Delete email_artifacts (references emails)
        if artifact_count > 0:
            supabase.table("email_artifacts").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            print(f"✓ Deleted {artifact_count} artifacts")

        # 3. Delete emails
        if email_count > 0:
            supabase.table("emails").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            print(f"✓ Deleted {email_count} emails")

        print()
        print("=" * 60)
        print("Cleanup Complete")
        print("=" * 60)
        print("All email data has been deleted from the database.")
        print()
        print("You can now run a fresh scrape:")
        print("  python src/scripts/scrape_emails.py --days-back 30")
        print()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
