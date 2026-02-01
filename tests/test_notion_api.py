"""Test Notion API fix for retrieve_previous_issues."""

import os
from dotenv import load_dotenv

load_dotenv()

# Test the Notion API fix
from src.services.notion_service import NotionService

print("=" * 70)
print("Testing Notion API - retrieve_previous_issues()")
print("=" * 70)

try:
    notion = NotionService()
    print("✓ NotionService initialized")
    print(f"  Database ID: {notion.database_id[:12]}...")

    print("\nCalling retrieve_previous_issues(limit=3)...")
    issues = notion.retrieve_previous_issues(limit=3)

    print(f"\n✓ SUCCESS! Retrieved {len(issues)} previous issues")

    if issues:
        print("\nFirst issue preview:")
        print(issues[0][:300] + "..." if len(issues[0]) > 300 else issues[0])
    else:
        print("\nNo published issues found in database.")
        print("This is OK if you haven't published any issues with Status='Published' yet.")

    print("\n" + "=" * 70)
    print("Notion API test completed successfully!")
    print("=" * 70)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "=" * 70)
    print("Notion API test FAILED")
    print("=" * 70)
