"""Supabase integration for storing and retrieving sauna news."""

import os
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

try:
    from supabase import create_client, Client
except ImportError:
    print("Warning: supabase-py not installed. Run: pip install supabase")
    Client = None


class NewsItem:
    """Represents a news item."""

    def __init__(
        self,
        title: str,
        summary: str,
        source_url: Optional[str] = None,
        published_at: Optional[datetime] = None,
        news_type: str = "other",
        venue_name: Optional[str] = None,
        is_featured: bool = False,
    ):
        self.title = title
        self.summary = summary
        self.source_url = source_url
        self.published_at = published_at
        self.news_type = news_type
        self.venue_name = venue_name
        self.is_featured = is_featured
        self.content_hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """Generate MD5 hash of title + summary for deduplication."""
        content = f"{self.title.lower().strip()}{self.summary.lower().strip()}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Supabase insertion."""
        return {
            "title": self.title,
            "summary": self.summary,
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "news_type": self.news_type,
            "venue_name": self.venue_name,
            "is_featured": self.is_featured,
            "content_hash": self.content_hash,
        }


class SupabaseService:
    """Service for interacting with Supabase for news storage."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """
        Initialize the Supabase service.

        Args:
            url: Supabase project URL (defaults to env var SUPABASE_URL)
            key: Supabase service role key (defaults to env var SUPABASE_KEY)
        """
        load_dotenv()

        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

        if Client is None:
            raise ImportError("supabase-py is not installed. Run: pip install supabase")

        self.client: Client = create_client(self.url, self.key)

    def insert_news(self, news_item: NewsItem) -> Optional[Dict[str, Any]]:
        """
        Insert a news item into the database.

        Args:
            news_item: NewsItem to insert

        Returns:
            Inserted row data or None if failed
        """
        try:
            result = self.client.table("sauna_news").insert(news_item.to_dict()).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error inserting news: {e}")
            return None

    def insert_many_news(self, news_items: List[NewsItem]) -> int:
        """
        Insert multiple news items into the database.

        Args:
            news_items: List of NewsItem objects

        Returns:
            Number of successfully inserted items
        """
        inserted_count = 0
        for item in news_items:
            if self.insert_news(item):
                inserted_count += 1
        return inserted_count

    def check_duplicate(self, content_hash: str) -> bool:
        """
        Check if a news item with the given content hash already exists.

        Args:
            content_hash: MD5 hash to check

        Returns:
            True if duplicate exists, False otherwise
        """
        try:
            result = (
                self.client.table("sauna_news")
                .select("id")
                .eq("content_hash", content_hash)
                .execute()
            )
            return len(result.data) > 0
        except Exception as e:
            print(f"Error checking duplicate: {e}")
            return False

    def get_recent_hashes(self, days: int = 14) -> List[str]:
        """
        Get content hashes from the last N days for deduplication.

        Args:
            days: Number of days to look back

        Returns:
            List of content hashes
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            result = (
                self.client.table("sauna_news")
                .select("content_hash")
                .gte("scraped_at", cutoff.isoformat())
                .execute()
            )
            return [row["content_hash"] for row in result.data]
        except Exception as e:
            print(f"Error fetching recent hashes: {e}")
            return []

    def get_recent_news(self, limit: int = 7, days: int = 14) -> List[Dict[str, Any]]:
        """
        Get recent news items for display.

        Args:
            limit: Maximum number of items to return
            days: Look back this many days

        Returns:
            List of news item dictionaries
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            result = (
                self.client.table("sauna_news")
                .select("*")
                .gte("scraped_at", cutoff.isoformat())
                .order("published_at", desc=True)
                .order("scraped_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data
        except Exception as e:
            print(f"Error fetching recent news: {e}")
            return []

    def get_featured_news(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get featured news items.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of featured news item dictionaries
        """
        try:
            result = (
                self.client.table("sauna_news")
                .select("*")
                .eq("is_featured", True)
                .order("published_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data
        except Exception as e:
            print(f"Error fetching featured news: {e}")
            return []

    def mark_as_featured(self, news_id: str) -> bool:
        """
        Mark a news item as featured.

        Args:
            news_id: UUID of the news item

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.table("sauna_news").update({"is_featured": True}).eq(
                "id", news_id
            ).execute()
            return True
        except Exception as e:
            print(f"Error marking as featured: {e}")
            return False

    def delete_old_news(self, days: int = 30) -> int:
        """
        Delete news items older than N days (cleanup).

        Args:
            days: Delete items older than this many days

        Returns:
            Number of deleted items
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            result = (
                self.client.table("sauna_news")
                .delete()
                .lt("scraped_at", cutoff.isoformat())
                .execute()
            )
            return len(result.data) if result.data else 0
        except Exception as e:
            print(f"Error deleting old news: {e}")
            return 0
