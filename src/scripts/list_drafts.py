#!/usr/bin/env python3
"""List all newsletter drafts from Notion database."""

import os
import sys
from datetime import datetime
from notion_client import Client


def format_date(iso_date: str) -> str:
    """Format ISO date to readable format."""
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime('%B %d, %Y %H:%M UTC')
    except:
        return iso_date


def normalize_id(id_str: str) -> str:
    """Remove dashes from ID for comparison."""
    return id_str.replace('-', '')


def main():
    """List all newsletter drafts from Notion."""
    # Get credentials
    api_key = os.getenv('NOTION_API_KEY')
    database_id = os.getenv('NOTION_DRAFT_NEWSLETTERS_DB_ID')

    if not api_key:
        print('❌ NOTION_API_KEY not found in environment')
        sys.exit(1)

    if not database_id:
        print('❌ NOTION_DRAFT_NEWSLETTERS_DB_ID not found in environment')
        sys.exit(1)

    # Initialize client
    client = Client(auth=api_key)

    try:
        # Get database info
        db_info = client.databases.retrieve(database_id=database_id)
        db_title = db_info.get('title', [{}])[0].get('text', {}).get('content', 'Unknown')

        print(f'\n📊 Notion Database: {db_title}')
        print(f'🔗 Database ID: {database_id[:8]}...\n')

        # Search for all pages
        response = client.search(
            sort={
                'direction': 'descending',
                'timestamp': 'last_edited_time'
            },
            page_size=50
        )

        # Filter for pages in our database
        clean_db_id = normalize_id(database_id)
        db_pages = []

        for page in response['results']:
            parent = page.get('parent', {})
            parent_id = parent.get('database_id') or parent.get('data_source_id')

            if parent_id and normalize_id(parent_id) == clean_db_id:
                db_pages.append(page)

        if not db_pages:
            print('📭 No drafts found in database\n')
            return

        print(f'✅ Found {len(db_pages)} draft(s)\n')
        print('─' * 80)

        # Display each draft
        for i, page in enumerate(db_pages, 1):
            props = page.get('properties', {})

            # Extract properties
            title = 'Untitled'
            if 'Name' in props and props['Name'].get('title'):
                if props['Name']['title']:
                    title = props['Name']['title'][0]['text']['content']

            issue_date = 'No date'
            if 'Issue Date' in props and props['Issue Date'].get('date'):
                issue_date = format_date(props['Issue Date']['date']['start'])

            status = 'No status'
            if 'Status' in props and props['Status'].get('select'):
                if props['Status']['select'] and 'name' in props['Status']['select']:
                    status = props['Status']['select']['name']

            run_id = 'No run ID'
            if 'Run ID' in props and props['Run ID'].get('rich_text'):
                if props['Run ID']['rich_text']:
                    run_id = props['Run ID']['rich_text'][0]['text']['content']

            last_edited = format_date(page.get('last_edited_time', ''))
            page_id = page['id']

            # Status emoji
            status_emoji = {
                'Draft': '📝',
                'Published': '✅',
                'Archived': '📦'
            }.get(status, '📄')

            print(f'\n{i}. {status_emoji} {title}')
            print(f'   📅 Issue Date: {issue_date}')
            print(f'   🏷️  Status: {status}')
            print(f'   🆔 Run ID: {run_id}')
            print(f'   ✏️  Last Edited: {last_edited}')
            print(f'   🔗 Page ID: {page_id}')

        print('\n' + '─' * 80)
        print(f'\n💡 Tip: Use /view-draft [run-id] to see draft content')
        print(f'💡 Tip: Use /run-draft to create a new draft\n')

    except Exception as e:
        print(f'\n❌ Error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
