#!/usr/bin/env python3
"""
Generate Gmail OAuth2 token for the sauna newsletter project.

This script performs a one-time OAuth2 authentication flow to generate
a token.json file that allows the application to access Gmail.

Prerequisites:
1. Create a Google Cloud Project at https://console.cloud.google.com
2. Enable the Gmail API
3. Create OAuth2 credentials (Desktop app type)
4. Download credentials.json and place in project root

Usage:
    python src/scripts/generate_gmail_token.py

The script will:
1. Open a browser for Google authentication
2. Request permission to read Gmail
3. Generate token.json in the project root
4. Display success message

After completion, token.json will be used by gmail_service.py for authentication.
"""

import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail API scopes (read-only access)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# File paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"


def main():
    """Generate Gmail OAuth2 token."""
    print("=" * 60)
    print("Gmail OAuth2 Token Generator")
    print("=" * 60)
    print()

    # Check for credentials.json
    if not CREDENTIALS_PATH.exists():
        print("ERROR: credentials.json not found!")
        print()
        print("To set up Gmail authentication:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create a new OAuth2 Client ID (Desktop app type)")
        print("3. Download the credentials JSON file")
        print(f"4. Save it as: {CREDENTIALS_PATH}")
        print()
        sys.exit(1)

    # Check if token already exists
    if TOKEN_PATH.exists():
        print(f"WARNING: token.json already exists at {TOKEN_PATH}")
        response = input("Do you want to regenerate it? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(0)

    print("Starting OAuth2 flow...")
    print("A browser window will open for authentication.")
    print()

    try:
        # Run OAuth flow
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_PATH),
            SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Save token
        with open(TOKEN_PATH, 'w') as token_file:
            token_file.write(creds.to_json())

        print()
        print("=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"Token saved to: {TOKEN_PATH}")
        print()
        print("You can now run:")
        print("  python src/scripts/scrape_emails.py")
        print()
        print("IMPORTANT: Add token.json to .gitignore to keep credentials secure!")
        print()

    except Exception as e:
        print()
        print("=" * 60)
        print("ERROR!")
        print("=" * 60)
        print(f"Failed to generate token: {e}")
        print()
        print("Troubleshooting:")
        print("- Ensure credentials.json is valid")
        print("- Check that Gmail API is enabled in Google Cloud Console")
        print("- Verify OAuth2 consent screen is configured")
        sys.exit(1)


if __name__ == "__main__":
    main()
