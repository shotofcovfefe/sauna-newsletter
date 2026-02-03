#!/usr/bin/env python3
"""Clear all news from the sauna_news table."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path and load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from src.services.supabase_service import SupabaseService


def main():
    """Clear all news items from the database."""
    print("=" * 70)
    print("CLEAR ALL SAUNA NEWS")
    print("=" * 70)

    try:
        supabase_service = SupabaseService()
        print("✓ Connected to Supabase")
    except Exception as e:
        print(f"✗ Error connecting to Supabase: {e}")
        sys.exit(1)

    # Delete all records
    try:
        response = supabase_service.client.table("sauna_news").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        deleted_count = len(response.data) if response.data else 0
        print(f"✓ Deleted {deleted_count} news items")
    except Exception as e:
        print(f"✗ Error deleting news: {e}")
        sys.exit(1)

    print("=" * 70)
    print("Done! Database cleared.")
    print("=" * 70)


if __name__ == "__main__":
    main()
