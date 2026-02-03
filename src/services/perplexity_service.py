"""Perplexity API integration for web search."""

import os
import requests
from typing import List, Optional
from ..models.types import SearchQuery, PerplexityResult


class PerplexityService:
    """Service for interacting with the Perplexity API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Perplexity service.

        Args:
            api_key: Perplexity API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY not found")

        self.base_url = "https://api.perplexity.ai"
        # Updated model name - check https://docs.perplexity.ai/guides/model-cards
        self.model = "sonar"  # or "sonar-pro" for better quality

    def search(self, query: SearchQuery) -> PerplexityResult:
        """
        Execute a search query using Perplexity.

        Args:
            query: SearchQuery object

        Returns:
            PerplexityResult with answer and sources
        """
        # Build the enhanced prompt
        prompt = self._build_prompt(query)

        # Call Perplexity API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a factual research assistant for London sauna news. Extract and quote relevant information EXACTLY as stated in sources. Do not paraphrase, interpret, or summarize - copy verbatim text. Include source URLs."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "return_citations": True,
            "search_recency_filter": "week"  # Only surface results from the past 7 days
        }

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        # Better error handling
        if response.status_code != 200:
            error_detail = response.text
            raise Exception(f"Perplexity API error ({response.status_code}): {error_detail}")

        response.raise_for_status()

        result_data = response.json()

        # Extract answer and sources
        answer = result_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = result_data.get("citations", [])

        return PerplexityResult(
            query=query.query,
            answer=answer,
            sources=citations,
            raw_response=result_data
        )

    def _build_prompt(self, query: SearchQuery) -> str:
        """
        Build an enhanced prompt for Perplexity.

        Args:
            query: SearchQuery object

        Returns:
            Formatted prompt string
        """
        prompt_parts = [query.query]

        # Add context if provided
        if query.context:
            prompt_parts.append(f"\nContext: {query.context}")

        # Add specific instructions
        prompt_parts.append("""
CRITICAL: Extract information EXACTLY as stated in sources. Quote verbatim. Do NOT paraphrase or interpret.

Please provide:
1. Direct quotes or exact facts from sources (copy word-for-word)
2. Source URLs for each fact
3. Exact dates if stated (event dates, opening dates, etc.)
4. Type: EVENT, NEWS, OPENING, CLOSURE, or OTHER

For events, extract verbatim:
- Event name (exact wording)
- Venue name (exact wording)
- Date(s) and time(s) as written
- Booking URL

For news/openings/closures, extract verbatim:
- What is stated (quote directly)
- Where (venue/location as written)
- When (date/timeframe as written)
- Source URL

ACCURACY RULE: If source says "runs five sites" do NOT interpret as "announces five-site expansion".
Copy the exact text from the source.
""")

        return "\n".join(prompt_parts)

    def search_multiple(
        self,
        queries: List[SearchQuery],
        max_concurrent: int = 5
    ) -> List[PerplexityResult]:
        """
        Execute multiple search queries sequentially.

        Args:
            queries: List of SearchQuery objects
            max_concurrent: Rate limiting - max queries per batch (for future async implementation)

        Returns:
            List of PerplexityResult objects
        """
        results = []

        # Execute ALL queries (not just first max_concurrent!)
        # Note: This is sequential for now, but processes all queries
        for i, query in enumerate(queries):
            try:
                print(f"  [{i+1}/{len(queries)}] {query.query[:60]}...")
                result = self.search(query)
                results.append(result)
            except Exception as e:
                print(f"  Error searching '{query.query}': {e}")
                # Create empty result on error
                results.append(
                    PerplexityResult(
                        query=query.query,
                        answer=f"Error: {str(e)}",
                        sources=[]
                    )
                )

        return results
