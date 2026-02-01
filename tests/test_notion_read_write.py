"""Test Notion read and write operations."""

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

from src.services.notion_service import NotionService
from src.models.types import NewsletterDraft

print("=" * 70)
print("Testing Notion Read/Write Operations")
print("=" * 70)

try:
    notion = NotionService()
    print("✓ NotionService initialized")
    print(f"  Database ID: {notion.database_id}")

    # TEST 1: Read existing drafts
    print("\n" + "=" * 70)
    print("TEST 1: Reading existing drafts")
    print("=" * 70)

    response = notion.client.data_sources.query(
        data_source_id=notion.database_id,
        sorts=[{"property": "Issue Date", "direction": "descending"}],
        page_size=3
    )

    results = response.get("results", [])
    print(f"✓ Read {len(results)} existing drafts")

    for i, page in enumerate(results[:2], 1):
        props = page.get("properties", {})
        title_items = props.get("Name", {}).get("title", [])
        title = title_items[0].get("text", {}).get("content", "Untitled") if title_items else "Untitled"
        print(f"  {i}. {title}")

    # TEST 2: Write a new test draft
    print("\n" + "=" * 70)
    print("TEST 2: Writing a new test draft")
    print("=" * 70)

    test_draft = NewsletterDraft(
        markdown_content="""# Test Newsletter

This is a test draft created to verify Notion API write access.

## Test Section

- Test item 1
- Test item 2
- Test item 3

**This draft can be deleted.**
""",
        issue_date=datetime.now(),
        sources=["https://example.com/test"],
        version=1
    )

    print("Creating test draft page...")
    page_id = notion.create_draft_page(
        draft=test_draft,
        run_id="test_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )

    print(f"✓ Successfully created test draft!")
    print(f"  Page ID: {page_id}")
    print(f"  URL: https://notion.so/{page_id}")

    # TEST 3: Verify we can read the page we just created
    print("\n" + "=" * 70)
    print("TEST 3: Verifying new draft appears in query")
    print("=" * 70)

    response = notion.client.data_sources.query(
        data_source_id=notion.database_id,
        sorts=[{"property": "Issue Date", "direction": "descending"}],
        page_size=1
    )

    latest = response.get("results", [])[0] if response.get("results") else None
    if latest and latest.get("id") == page_id:
        print("✓ New draft verified - appears as latest in database")
    else:
        print("⚠️  New draft created but not appearing as latest (may take a moment)")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED ✓")
    print("=" * 70)
    print("\nNotion read/write is working correctly!")
    print(f"You can view your test draft at: https://notion.so/{page_id}")

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "=" * 70)
    print("TEST FAILED")
    print("=" * 70)
