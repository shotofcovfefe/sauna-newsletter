"""Gmail API service for fetching and processing emails."""

import os
import base64
from email import message_from_bytes
from email.message import Message
from typing import List, Optional
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def load_credentials(token_path: str, scopes: List[str]) -> Credentials:
    """
    Load OAuth2 credentials from token.json, refreshing if needed.

    Args:
        token_path: Path to token.json file
        scopes: List of required OAuth scopes

    Returns:
        Google OAuth2 Credentials object

    Raises:
        FileNotFoundError: If token.json doesn't exist
    """
    if not os.path.exists(token_path):
        raise FileNotFoundError(
            f"Token file not found at {token_path}. "
            "Run src/scripts/generate_gmail_token.py first."
        )

    creds = Credentials.from_authorized_user_file(token_path, scopes)

    # Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save refreshed credentials
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

    return creds


class GmailClient:
    """Client for interacting with Gmail API."""

    def __init__(self, token_path: str = "token.json") -> None:
        """
        Initialize Gmail client with OAuth2 credentials.

        Args:
            token_path: Path to token.json file (default: "token.json")
        """
        self.token_path = token_path
        self.creds = load_credentials(self.token_path, SCOPES)
        self.service = build("gmail", "v1", credentials=self.creds)

    def fetch_messages(
        self,
        query: Optional[str] = None,
        max_results: int = 100
    ) -> List[Message]:
        """
        Fetch all messages from Gmail matching the optional query.

        Uses pagination to handle large result sets. Fetches full message
        content including headers and body.

        Args:
            query: Optional Gmail query string (e.g., "after:1234567890", "is:unread")
            max_results: Maximum messages per API call (default: 100)

        Returns:
            List of email.message.Message objects

        Raises:
            HttpError: If Gmail API request fails
        """
        messages: List[Message] = []
        page_token = None

        try:
            while True:
                # Build request parameters
                list_args = {
                    "userId": "me",
                    "maxResults": max_results,
                }
                if query:
                    list_args["q"] = query
                if page_token:
                    list_args["pageToken"] = page_token

                # Fetch message list
                response = self.service.users().messages().list(**list_args).execute()
                raw_messages = response.get("messages", [])

                # Fetch full message details
                for msg_info in raw_messages:
                    msg_id = msg_info["id"]
                    detail = self.service.users().messages().get(
                        userId="me",
                        id=msg_id,
                        format="raw"
                    ).execute()

                    # Decode raw message
                    msg_bytes = base64.urlsafe_b64decode(detail["raw"])
                    msg_obj = message_from_bytes(msg_bytes)
                    messages.append(msg_obj)

                # Check for more pages
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        except HttpError as error:
            print(f"Gmail API error: {error}")
            raise

        return messages

    def get_email_body(self, message: Message) -> str:
        """
        Extract plain text body from email message.

        Handles multipart messages, HTML conversion, and content decoding.

        Args:
            message: email.message.Message object

        Returns:
            Plain text email body
        """
        body = ""

        # Handle multipart messages
        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                # Get plain text parts
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode('utf-8', errors='ignore')
                    except Exception as e:
                        print(f"Error decoding text/plain part: {e}")

                # Fallback to HTML if no plain text
                elif content_type == "text/html" and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            html_content = payload.decode('utf-8', errors='ignore')
                            # Import here to avoid dependency if not needed
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(html_content, 'html.parser')
                            body += soup.get_text(separator='\n', strip=True)
                    except Exception as e:
                        print(f"Error decoding text/html part: {e}")

        else:
            # Handle non-multipart messages
            content_type = message.get_content_type()
            try:
                payload = message.get_payload(decode=True)
                if payload:
                    if content_type == "text/plain":
                        body = payload.decode('utf-8', errors='ignore')
                    elif content_type == "text/html":
                        from bs4 import BeautifulSoup
                        html_content = payload.decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(html_content, 'html.parser')
                        body = soup.get_text(separator='\n', strip=True)
            except Exception as e:
                print(f"Error decoding message body: {e}")

        return body.strip()

    def get_header(self, message: Message, header_name: str) -> Optional[str]:
        """
        Get email header value.

        Args:
            message: email.message.Message object
            header_name: Header name (e.g., "From", "Subject", "Message-ID")

        Returns:
            Header value or None if not found
        """
        return message.get(header_name)

    def format_date_for_query(self, timestamp: str) -> str:
        """
        Convert ISO8601 timestamp to Gmail query format.

        Gmail's "after:" query expects Unix timestamp.

        Args:
            timestamp: ISO8601 timestamp string

        Returns:
            Unix timestamp string
        """
        from dateutil import parser as date_parser
        dt = date_parser.isoparse(timestamp)
        return str(int(dt.timestamp()))
