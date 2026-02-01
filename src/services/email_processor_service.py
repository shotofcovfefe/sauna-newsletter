"""Email processing service for compressing and storing emails in Supabase."""

import os
import re
import time
from datetime import datetime
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional, Dict, Any

from supabase import create_client, Client
from bs4 import BeautifulSoup
from google import genai


class EmailProcessorService:
    """Service for processing and compressing emails using LLM."""

    def __init__(self, supabase_client: Client, gemini_api_key: str):
        """
        Initialize email processor.

        Args:
            supabase_client: Initialized Supabase client
            gemini_api_key: Gemini API key for LLM operations
        """
        self.supabase = supabase_client

        # Initialize Gemini client (new SDK)
        self.client = genai.Client(api_key=gemini_api_key)
        # Use gemini-3-flash-preview
        self.model_name = 'gemini-3-flash-preview'

        # Rate limiting: add delay between API calls to avoid quota exhaustion
        self.request_delay = 2.0  # 2 seconds between requests to stay under quota

    def _call_gemini_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        Call Gemini API with retry logic for rate limiting.

        Args:
            prompt: The prompt to send to Gemini
            max_retries: Maximum number of retry attempts

        Returns:
            Response text or None if all retries failed
        """
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                # Success - add delay before next call to stay under quota
                time.sleep(self.request_delay)
                return response.text.strip()

            except Exception as e:
                error_str = str(e)

                # Check if it's a 429 rate limit error
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    # Extract retry delay from error if available
                    if "retryDelay" in error_str:
                        # Parse retry delay (e.g., "59s")
                        import re
                        match = re.search(r"'retryDelay': '(\d+)s'", error_str)
                        if match:
                            retry_delay = int(match.group(1))
                        else:
                            retry_delay = 60  # Default to 60 seconds
                    else:
                        # Exponential backoff: 5s, 10s, 20s
                        retry_delay = 5 * (2 ** attempt)

                    if attempt < max_retries - 1:
                        print(f"  Rate limit hit. Waiting {retry_delay}s before retry {attempt + 1}/{max_retries}...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"  Max retries reached. Giving up on this API call.")
                        return None
                else:
                    # Non-rate-limit error, don't retry
                    print(f"  API error (non-rate-limit): {e}")
                    return None

        return None

    def email_already_processed(self, message_id: str) -> bool:
        """
        Check if email has already been processed.

        Args:
            message_id: Gmail Message-ID header

        Returns:
            True if email exists in database, False otherwise
        """
        try:
            result = (
                self.supabase.table("emails")
                .select("id")
                .eq("message_id", message_id)
                .limit(1)
                .execute()
            )
            return bool(result.data)
        except Exception as e:
            print(f"Error checking if email processed: {e}")
            return False

    def clean_email_body(self, raw_body: str) -> str:
        """
        Clean email body by removing URLs, excessive whitespace, and formatting.

        Args:
            raw_body: Raw email body text

        Returns:
            Cleaned email body
        """
        # Remove HTML tags if any remain
        soup = BeautifulSoup(raw_body, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)

        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)

        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)

        return text.strip()

    def compress_email_content(self, raw_body: str) -> str:
        """
        Use Gemini to compress email content into key points.

        Args:
            raw_body: Raw email body text

        Returns:
            LLM-compressed content (key points without HTML/graphics)
        """
        prompt = f"""You are an email content extractor for a London sauna newsletter.

Extract the key points from emails, focusing on:
- Events (dates, times, locations, names)
- News and announcements
- Openings, closures, or changes
- Special offers or promotions

Remove all:
- HTML formatting and tags
- Image references and graphics
- Excessive whitespace
- Marketing fluff and boilerplate

Summarize in 3-7 concise bullet points. Be specific about dates, times, and venue names if mentioned.

Email content:
{raw_body[:3000]}"""

        try:
            response_text = self._call_gemini_with_retry(prompt)
            if response_text:
                return response_text
            else:
                # API call failed after retries, use fallback
                return self.clean_email_body(raw_body)[:500]
        except Exception as e:
            print(f"Error compressing email content: {e}")
            # Fallback: return cleaned body if LLM fails
            return self.clean_email_body(raw_body)[:500]

    def classify_sauna_relevance(self, content: str, subject: str) -> Dict[str, Any]:
        """
        Use Gemini to classify if email is sauna/wellness related and rate confidence.

        Args:
            content: Email content (compressed or raw)
            subject: Email subject line

        Returns:
            Dict with 'is_sauna_related' (bool), 'confidence_score' (float), and 'summary' (str)
        """
        prompt = f"""You are a content classifier for a London sauna newsletter.

Analyze emails to determine if they're related to saunas, wellness, or spa/thermal bathing in London.

Respond in this exact format:
RELEVANT: yes/no
CONFIDENCE: 0.0-1.0
SUMMARY: One-line summary of the email content

Rules:
- Mark as relevant if it mentions: saunas, spas, thermal bathing, wellness events, bathhouses, steam rooms
- Mark as NOT relevant if it's: promotions for unrelated businesses, newsletters about other topics
- Confidence should be high (0.8+) for explicit sauna mentions, medium (0.5-0.7) for general wellness, low (0.3-0.4) for tangential

Subject: {subject}

Content:
{content[:1000]}"""

        try:
            response_text = self._call_gemini_with_retry(prompt)

            if not response_text:
                # API call failed after retries, use conservative fallback
                return {
                    "is_sauna_related": True,
                    "confidence_score": 0.3,
                    "summary": "Email content (classification failed - rate limit)"
                }

            # Parse response
            lines = response_text.split('\n')
            is_relevant = False
            confidence = 0.5
            summary = "Email content"

            for line in lines:
                if line.startswith("RELEVANT:"):
                    is_relevant = "yes" in line.lower()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(re.search(r'[\d.]+', line).group())
                    except:
                        confidence = 0.5
                elif line.startswith("SUMMARY:"):
                    summary = line.replace("SUMMARY:", "").strip()

            return {
                "is_sauna_related": is_relevant,
                "confidence_score": min(max(confidence, 0.0), 1.0),  # Clamp to [0, 1]
                "summary": summary
            }

        except Exception as e:
            print(f"Error classifying sauna relevance: {e}")
            # Conservative fallback: mark as potentially relevant
            return {
                "is_sauna_related": True,
                "confidence_score": 0.3,
                "summary": "Email content (classification failed)"
            }

    def process_email(self, message: Message, raw_body: str) -> Optional[Dict[str, Any]]:
        """
        Process a single email: extract metadata, compress content, classify, and store.

        Args:
            message: email.message.Message object
            raw_body: Plain text email body

        Returns:
            Dict with email_id and artifact_id if successful, None if skipped/failed
        """
        # Extract metadata
        message_id = message.get("Message-ID", "").strip()
        if not message_id:
            print("Skipping email without Message-ID")
            return None

        # Check if already processed
        if self.email_already_processed(message_id):
            print(f"Email already processed: {message_id}")
            return None

        # Extract sender info
        from_header = message.get("From", "")
        sender_name, sender_email = parseaddr(from_header)

        # Extract subject
        subject = message.get("Subject", "")

        # Extract date
        date_header = message.get("Date")
        email_date = None
        if date_header:
            try:
                email_date = parsedate_to_datetime(date_header)
            except Exception as e:
                print(f"Error parsing date: {e}")

        # Store raw email
        try:
            email_row = {
                "message_id": message_id,
                "sender": sender_email,
                "sender_name": sender_name,
                "subject": subject,
                "date": email_date.isoformat() if email_date else None,
                "raw_body": raw_body,
                "processed_at": datetime.utcnow().isoformat()
            }

            email_result = self.supabase.table("emails").insert(email_row).execute()
            email_id = email_result.data[0]["id"]

        except Exception as e:
            print(f"Error storing email: {e}")
            return None

        # Compress content
        compressed_content = self.compress_email_content(raw_body)

        # Classify relevance
        classification = self.classify_sauna_relevance(compressed_content, subject)

        # Store artifact
        try:
            artifact_row = {
                "email_id": email_id,
                "compressed_content": compressed_content,
                "summary": classification["summary"],
                "is_sauna_related": classification["is_sauna_related"],
                "confidence_score": classification["confidence_score"],
                "gemini_model": "gemini-2.0-flash-exp",
                "processed_at": datetime.utcnow().isoformat()
            }

            artifact_result = self.supabase.table("email_artifacts").insert(artifact_row).execute()
            artifact_id = artifact_result.data[0]["id"]

            return {
                "email_id": email_id,
                "artifact_id": artifact_id,
                "is_sauna_related": classification["is_sauna_related"],
                "confidence_score": classification["confidence_score"]
            }

        except Exception as e:
            print(f"Error storing artifact: {e}")
            return None

    def get_latest_email_date(self) -> Optional[str]:
        """
        Get the date of the most recent email in our database.

        Uses the email's actual date (when it was sent), not when we processed it.
        This ensures we fetch all emails after the last one we have, regardless of
        when we processed them.

        Returns:
            ISO8601 timestamp string or None if no emails processed
        """
        try:
            result = (
                self.supabase.table("emails")
                .select("date")
                .order("date", desc=True)
                .limit(1)
                .execute()
            )

            if result.data and result.data[0].get("date"):
                return result.data[0]["date"]

        except Exception as e:
            print(f"Error getting latest email date: {e}")

        return None

    def get_unused_artifacts(self, min_confidence: float = 0.5, days_back: int = None) -> list:
        """
        Get email artifacts that haven't been used in any newsletter yet.

        Args:
            min_confidence: Minimum confidence score for sauna-relevance
            days_back: Only include emails from the last N days (None = all emails)

        Returns:
            List of artifact dictionaries
        """
        try:
            # Query for sauna-related artifacts not in newsletter_artifacts
            result = self.supabase.rpc(
                'get_unused_email_artifacts',
                {
                    'min_confidence': min_confidence,
                    'days_back': days_back
                }
            ).execute()

            return result.data or []

        except Exception as e:
            # Fallback: manual query if RPC doesn't exist
            print(f"RPC call failed, using fallback query: {e}")

            from datetime import datetime, timedelta, timezone

            # Get all sauna-related artifacts
            query = (
                self.supabase.table("email_artifacts")
                .select("*, emails!inner(date, sender, subject)")
                .eq("is_sauna_related", True)
                .gte("confidence_score", min_confidence)
            )

            # Add date filter if specified
            if days_back is not None:
                cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
                query = query.gte("emails.date", cutoff_date)

            artifacts = query.execute()

            # Filter out ones already used
            unused = []
            for artifact in artifacts.data or []:
                used_check = (
                    self.supabase.table("newsletter_artifacts")
                    .select("artifact_id")
                    .eq("artifact_id", artifact["id"])
                    .limit(1)
                    .execute()
                )

                if not used_check.data:
                    unused.append(artifact)

            return unused

    def mark_artifacts_used(self, artifact_ids: list, run_id: str) -> None:
        """
        Mark email artifacts as used in a newsletter run.

        Args:
            artifact_ids: List of artifact UUIDs
            run_id: Newsletter run ID
        """
        try:
            rows = [
                {
                    "artifact_id": artifact_id,
                    "run_id": run_id,
                    "created_at": datetime.utcnow().isoformat()
                }
                for artifact_id in artifact_ids
            ]

            self.supabase.table("newsletter_artifacts").insert(rows).execute()

        except Exception as e:
            print(f"Error marking artifacts as used: {e}")
