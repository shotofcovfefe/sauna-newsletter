"""Search for accessible databases via Notion API."""

import os
from dotenv import load_dotenv

load_dotenv()

from notion_client import Client

print("=" * 70)
print("Searching for accessible Notion databases")
print("=" * 70)

try:
    client = Client(auth=os.getenv("NOTION_API_KEY"))

    # Search for data sources (databases in 2025 API)
    print("\nSearching for data sources (databases)...")
    response = client.search(
        filter={"property": "object", "value": "data_source"}
    )

    databases = response.get("results", [])
    print(f"\n✓ Found {len(databases)} accessible databases")

    if databases:
        print("\n" + "=" * 70)
        print("ACCESSIBLE DATABASES:")
        print("=" * 70)

        for i, db in enumerate(databases, 1):
            db_id = db.get("id")
            title_items = db.get("title", [])
            title = title_items[0].get("text", {}).get("content", "Untitled") if title_items else "Untitled"

            print(f"\n{i}. {title}")
            print(f"   ID: {db_id}")

            # Check if this matches our database ID
            expected_id = os.getenv("NOTION_DRAFT_NEWSLETTERS_DB_ID")
            if expected_id and (db_id == expected_id or db_id.replace("-", "") == expected_id.replace("-", "")):
                print("   ⭐ THIS IS YOUR CONFIGURED DATABASE!")
    else:
        print("\n⚠️  No databases found. Your integration may not be connected to any databases.")
        print("   Please share a database with your Notion integration.")

    print("\n" + "=" * 70)
    print(f"Expected database ID: {os.getenv('NOTION_DRAFT_NEWSLETTERS_DB_ID')}")
    print("=" * 70)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
