"""Test different methods of creating Notion pages."""

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

from notion_client import Client

db_id = os.getenv("NOTION_DRAFT_NEWSLETTERS_DB_ID")
api_key = os.getenv("NOTION_API_KEY")

print("=" * 70)
print("Testing Notion Page Creation Methods")
print("=" * 70)
print(f"Database ID: {db_id}")
print()

client = Client(auth=api_key)

# Try method 1: pages.create with database_id parent
print("METHOD 1: pages.create with database_id parent")
print("-" * 70)

try:
    response = client.pages.create(
        parent={"database_id": db_id},
        properties={
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": "Test - Method 1 (database_id)"
                        }
                    }
                ]
            },
            "Status": {
                "select": {
                    "name": "Draft"
                }
            },
            "Issue Date": {
                "date": {
                    "start": datetime.now().isoformat()
                }
            }
        }
    )
    print(f"✓ SUCCESS! Page ID: {response['id']}")
    print(f"  URL: https://notion.so/{response['id']}")
except Exception as e:
    print(f"✗ FAILED: {e}")

# Try method 2: pages.create with data_source_id parent
print("\nMETHOD 2: pages.create with data_source_id parent")
print("-" * 70)

try:
    response = client.pages.create(
        parent={"data_source_id": db_id},
        properties={
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": "Test - Method 2 (data_source_id)"
                        }
                    }
                ]
            },
            "Status": {
                "select": {
                    "name": "Draft"
                }
            },
            "Issue Date": {
                "date": {
                    "start": datetime.now().isoformat()
                }
            }
        }
    )
    print(f"✓ SUCCESS! Page ID: {response['id']}")
    print(f"  URL: https://notion.so/{response['id']}")
except Exception as e:
    print(f"✗ FAILED: {e}")

print("\n" + "=" * 70)
