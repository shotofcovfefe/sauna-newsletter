#!/usr/bin/env python3
"""
Scrape and process emails from Gmail for the sauna newsletter.

This script:
1. Fetches emails from Gmail (incremental based on email date)
2. Extracts plain text content
3. Compresses content using Gemini Flash
4. Classifies sauna-relevance
5. Stores emails and artifacts in Supabase
6. Tracks processed emails to avoid duplicates

Incremental Fetching Logic:
- If emails exist in database: Fetch emails after the latest email date
- If database is empty: Fetch emails from the last N days (default: 30)
- Never relies on Gmail "read/unread" status

Usage:
    python src/scripts/scrape_emails.py                    # Process new emails
    python src/scripts/scrape_emails.py --limit 10         # Process max 10 emails
    python src/scripts/scrape_emails.py --days-back 7      # First run: fetch last 7 days
    python src/scripts/scrape_emails.py --query "from:venue@example.com"  # Custom query

Environment Variables Required:
    SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY

Files Required:
    - token.json (generate with src/scripts/generate_gmail_token.py)
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.services.gmail_service import GmailClient
from src.services.email_processor_service import EmailProcessorService


def main():
    """Main entry point for email scraper."""
    parser = argparse.ArgumentParser(
        description="Scrape and process emails from Gmail"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of emails to process",
        default=None
    )
    parser.add_argument(
        "--query",
        help="Custom Gmail query (e.g., 'from:venue@example.com')",
        default=None
    )
    parser.add_argument(
        "--days-back",
        type=int,
        help="Force fetch emails from N days back (overrides incremental fetching)",
        default=None
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Verify required env vars
    required_vars = ["SUPABASE_URL", "SUPABASE_KEY", "GEMINI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these in your .env file")
        sys.exit(1)

    # Check for token.json
    token_path = Path("token.json")
    if not token_path.exists():
        print("ERROR: token.json not found!")
        print("\nRun this command first to generate OAuth token:")
        print("  python src/scripts/generate_gmail_token.py")
        sys.exit(1)

    print("=" * 60)
    print("Email Scraper - Sauna Newsletter")
    print("=" * 60)
    print()

    # Initialize services
    try:
        print("Initializing services...")
        gmail_client = GmailClient(token_path=str(token_path))
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        processor = EmailProcessorService(
            supabase_client=supabase,
            gemini_api_key=os.getenv("GEMINI_API_KEY")
        )
        print("✓ Services initialized")
        print()

    except Exception as e:
        print(f"ERROR: Failed to initialize services: {e}")
        sys.exit(1)

    # Build Gmail query
    if args.query:
        # Custom query overrides everything
        gmail_query = args.query
        print(f"Using custom query: {gmail_query}")
    elif args.days_back is not None:
        # --days-back explicitly provided: force fetch from that window (ignore incremental)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=args.days_back)
        timestamp = gmail_client.format_date_for_query(cutoff_date.isoformat())
        gmail_query = f"after:{timestamp}"
        print(f"Force fetching emails from last {args.days_back} days (incremental disabled).")
    else:
        # No flags: use incremental fetching
        latest_date = processor.get_latest_email_date()
        if latest_date:
            gmail_query = f"after:{gmail_client.format_date_for_query(latest_date)}"
            print(f"Fetching emails after: {latest_date} (incremental mode)")
        else:
            # No emails in DB: default to last 30 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            timestamp = gmail_client.format_date_for_query(cutoff_date.isoformat())
            gmail_query = f"after:{timestamp}"
            print(f"No previous emails found. Fetching emails from last 30 days.")

    print(f"Gmail query: {gmail_query}")
    print()

    # Fetch messages
    try:
        print("Fetching emails from Gmail...")
        messages = gmail_client.fetch_messages(
            query=gmail_query,
            max_results=100
        )

        total_fetched = len(messages)
        print(f"✓ Fetched {total_fetched} emails")
        print()

        if total_fetched == 0:
            print("No new emails to process.")
            sys.exit(0)

    except Exception as e:
        print(f"ERROR: Failed to fetch emails: {e}")
        sys.exit(1)

    # Apply limit if specified
    if args.limit and args.limit < len(messages):
        messages = messages[:args.limit]
        print(f"Processing first {args.limit} emails (--limit flag)")
        print()

    # Process emails
    processed_count = 0
    skipped_count = 0
    sauna_related_count = 0
    errors = []

    print("Processing emails...")
    print("-" * 60)

    for i, message in enumerate(messages, 1):
        message_id = message.get("Message-ID", "unknown")
        subject = message.get("Subject", "(no subject)")

        print(f"\n[{i}/{len(messages)}] {subject[:50]}...")

        try:
            # Extract body
            raw_body = gmail_client.get_email_body(message)

            if not raw_body:
                print("  ⚠ Skipping: No body content")
                skipped_count += 1
                continue

            # Process and store
            result = processor.process_email(message, raw_body)

            if result:
                processed_count += 1
                confidence = result["confidence_score"]
                is_relevant = result["is_sauna_related"]

                if is_relevant:
                    sauna_related_count += 1
                    print(f"  ✓ Processed (sauna-related, confidence: {confidence:.2f})")
                else:
                    print(f"  ✓ Processed (not sauna-related, confidence: {confidence:.2f})")
            else:
                skipped_count += 1
                print("  ⚠ Skipped (already processed or error)")

        except Exception as e:
            error_msg = f"Email {i}: {str(e)}"
            errors.append(error_msg)
            print(f"  ✗ Error: {e}")
            skipped_count += 1

    # Summary
    print()
    print("=" * 60)
    print("Email Scraping Complete")
    print("=" * 60)
    print(f"Total fetched:       {total_fetched}")
    print(f"Processed:           {processed_count}")
    print(f"Sauna-related:       {sauna_related_count}")
    print(f"Skipped:             {skipped_count}")
    print(f"Errors:              {len(errors)}")
    print()

    if errors:
        print("Errors encountered:")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")
        print()

    print("To use these emails in newsletters, they will be automatically")
    print("included in the next gather workflow as 'email' source candidates.")
    print()


if __name__ == "__main__":
    main()
