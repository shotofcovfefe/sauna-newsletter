"""Query Notion database for all drafts (not just published issues)."""

import os
from dotenv import load_dotenv

load_dotenv(override=True)

from src.services.notion_service import NotionService

print("=" * 70)
print("Querying Notion Database for Drafts")
print("=" * 70)

try:
    notion = NotionService()
    print("✓ NotionService initialized")
    print(f"  Database ID: {notion.database_id}")

    # Query for ALL pages (no filter)
    print("\nQuerying for all pages in database...")
    response = notion.client.data_sources.query(
        data_source_id=notion.database_id,
        sorts=[
            {
                "property": "Issue Date",
                "direction": "descending"
            }
        ],
        page_size=10
    )

    results = response.get("results", [])
    print(f"\n✓ Found {len(results)} pages in database")

    if results:
        print("\n" + "=" * 70)
        print("DRAFT DETAILS:")
        print("=" * 70)

        for i, page in enumerate(results, 1):
            props = page.get("properties", {})

            # Extract title
            title_prop = props.get("Name", {})
            title_items = title_prop.get("title", [])
            title = title_items[0].get("text", {}).get("content", "Untitled") if title_items else "Untitled"

            # Extract status
            status_prop = props.get("Status", {})
            status = status_prop.get("select", {}).get("name", "N/A") if status_prop.get("select") else "N/A"

            # Extract issue date
            date_prop = props.get("Issue Date", {})
            issue_date = date_prop.get("date", {}).get("start", "N/A") if date_prop.get("date") else "N/A"

            # Extract run ID
            run_id_prop = props.get("Run ID", {})
            run_id_items = run_id_prop.get("rich_text", [])
            run_id = run_id_items[0].get("text", {}).get("content", "N/A") if run_id_items else "N/A"

            print(f"\n{i}. {title}")
            print(f"   Status: {status}")
            print(f"   Issue Date: {issue_date}")
            print(f"   Run ID: {run_id}")
            print(f"   Page ID: {page['id']}")
    else:
        print("\nNo pages found in database.")

    print("\n" + "=" * 70)
    print("Query completed successfully!")
    print("=" * 70)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
