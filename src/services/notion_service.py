"""Notion API integration for publishing drafts."""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from notion_client import Client
from ..models.types import NewsletterDraft


class NotionService:
    """Service for interacting with Notion API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        database_id: Optional[str] = None
    ):
        """
        Initialize the Notion service.

        Args:
            api_key: Notion API key (defaults to env var)
            database_id: Notion database ID (defaults to env var)
        """
        self.api_key = api_key or os.getenv("NOTION_API_KEY")
        self.database_id = database_id or os.getenv("NOTION_DRAFT_NEWSLETTERS_DB_ID")

        if not self.api_key:
            raise ValueError("NOTION_API_KEY not found")
        if not self.database_id:
            raise ValueError("NOTION_DRAFT_NEWSLETTERS_DB_ID not found")

        self.client = Client(auth=self.api_key)

    def create_draft_page(
        self,
        draft: NewsletterDraft,
        run_id: str
    ) -> str:
        """
        Create a new page in the Newsletters database.

        Args:
            draft: NewsletterDraft object
            run_id: Unique run identifier

        Returns:
            Notion page ID
        """
        # Build page properties
        properties = {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": f"Draft - {draft.issue_date.strftime('%B %d, %Y')}"
                        }
                    }
                ]
            },
            "Issue Date": {
                "date": {
                    "start": draft.issue_date.isoformat()
                }
            },
            "Status": {
                "select": {
                    "name": "Draft"
                }
            },
            "Run ID": {
                "rich_text": [
                    {
                        "text": {
                            "content": run_id
                        }
                    }
                ]
            }
        }

        # Add spotlight venue if present
        if draft.spotlight_venue:
            properties["Spotlight Venue"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": draft.spotlight_venue
                        }
                    }
                ]
            }

        # Build page content (children blocks)
        children = self._markdown_to_blocks(draft.markdown_content)

        # Add sources section
        if draft.sources:
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Sources"}}]
                }
            })

            for url in draft.sources[:20]:  # Limit to 20 sources
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": url, "link": {"url": url}}
                            }
                        ]
                    }
                })

        # Create the page
        try:
            response = self.client.pages.create(
                parent={"data_source_id": self.database_id},
                properties=properties,
                children=children
            )
            return response["id"]
        except Exception as e:
            print(f"Error creating Notion page: {e}")
            raise

    def _markdown_to_blocks(self, markdown: str) -> List[Dict[str, Any]]:
        """
        Convert markdown to Notion blocks.

        This is a simple implementation - converts basic markdown to Notion blocks.

        Args:
            markdown: Markdown string

        Returns:
            List of Notion block objects
        """
        blocks = []
        lines = markdown.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                i += 1
                continue

            # Heading 1
            if line.startswith("# "):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                    }
                })

            # Heading 2
            elif line.startswith("## "):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                    }
                })

            # Heading 3
            elif line.startswith("### "):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": line[4:]}}]
                    }
                })

            # Bulleted list
            elif line.startswith("- ") or line.startswith("* "):
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": self._parse_rich_text(line[2:])
                    }
                })

            # Numbered list
            elif len(line) > 2 and line[0].isdigit() and line[1:3] == ". ":
                blocks.append({
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": self._parse_rich_text(line[3:])
                    }
                })

            # Quote
            elif line.startswith("> "):
                blocks.append({
                    "object": "block",
                    "type": "quote",
                    "quote": {
                        "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                    }
                })

            # Regular paragraph
            else:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": self._parse_rich_text(line)
                    }
                })

            i += 1

        return blocks

    def _parse_rich_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse text for basic markdown formatting (bold, italic, links).

        This is a simple parser - doesn't handle all edge cases.

        Args:
            text: Text string with markdown

        Returns:
            List of rich text objects
        """
        # For now, just return as plain text
        # A full implementation would parse **bold**, *italic*, [links](), etc.
        return [{"type": "text", "text": {"content": text}}]

    def get_spotlighted_venues(self) -> List[str]:
        """
        Get list of venues that have been spotlighted in published newsletters.

        Returns:
            List of venue names that have been spotlighted
        """
        try:
            # Query published newsletters
            response = self.client.data_sources.query(
                data_source_id=self.database_id,
                filter={
                    "property": "Status",
                    "select": {
                        "equals": "Published"
                    }
                },
                page_size=100  # Get all published issues
            )

            spotlighted = []
            for page in response.get("results", []):
                # Check if page has a "Spotlight Venue" property
                properties = page.get("properties", {})
                spotlight_prop = properties.get("Spotlight Venue", {})

                # Handle rich_text property
                if spotlight_prop.get("type") == "rich_text":
                    rich_text = spotlight_prop.get("rich_text", [])
                    if rich_text and len(rich_text) > 0:
                        venue_name = rich_text[0].get("plain_text", "").strip()
                        if venue_name:
                            spotlighted.append(venue_name)

            return spotlighted

        except Exception as e:
            print(f"Warning: Could not fetch spotlighted venues: {e}")
            return []

    def retrieve_previous_issues(self, limit: int = 5) -> List[str]:
        """
        Retrieve previous newsletter issues from Notion.

        Args:
            limit: Number of issues to retrieve

        Returns:
            List of markdown content strings
        """
        try:
            # Use data_sources.query instead of databases.query (2025 API)
            # In Notion API 2025+, databases became "data sources"
            response = self.client.data_sources.query(
                data_source_id=self.database_id,
                filter={
                    "property": "Status",
                    "select": {
                        "equals": "Published"
                    }
                },
                sorts=[
                    {
                        "property": "Issue Date",
                        "direction": "descending"
                    }
                ],
                page_size=limit
            )

            issues = []
            for page in response.get("results", []):
                # Get page content
                page_id = page["id"]
                content = self._get_page_markdown(page_id)
                if content:
                    issues.append(content)

            return issues

        except Exception as e:
            print(f"Error retrieving previous issues: {e}")
            return []

    def _get_page_markdown(self, page_id: str) -> Optional[str]:
        """
        Get markdown content from a Notion page.

        Args:
            page_id: Notion page ID

        Returns:
            Markdown string or None
        """
        try:
            # Retrieve page blocks
            blocks = self.client.blocks.children.list(block_id=page_id)

            markdown_lines = []
            for block in blocks.get("results", []):
                block_type = block.get("type")

                if block_type == "heading_1":
                    text = self._extract_text(block["heading_1"])
                    markdown_lines.append(f"# {text}")

                elif block_type == "heading_2":
                    text = self._extract_text(block["heading_2"])
                    markdown_lines.append(f"## {text}")

                elif block_type == "heading_3":
                    text = self._extract_text(block["heading_3"])
                    markdown_lines.append(f"### {text}")

                elif block_type == "paragraph":
                    text = self._extract_text(block["paragraph"])
                    markdown_lines.append(text)

                elif block_type == "bulleted_list_item":
                    text = self._extract_text(block["bulleted_list_item"])
                    markdown_lines.append(f"- {text}")

                elif block_type == "numbered_list_item":
                    text = self._extract_text(block["numbered_list_item"])
                    markdown_lines.append(f"1. {text}")

                elif block_type == "quote":
                    text = self._extract_text(block["quote"])
                    markdown_lines.append(f"> {text}")

            return "\n".join(markdown_lines)

        except Exception as e:
            print(f"Error getting page markdown: {e}")
            return None

    def _extract_text(self, block_content: Dict[str, Any]) -> str:
        """Extract plain text from a Notion block."""
        rich_text = block_content.get("rich_text", [])
        return "".join([rt.get("text", {}).get("content", "") for rt in rich_text])
