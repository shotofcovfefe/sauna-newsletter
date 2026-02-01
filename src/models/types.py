"""Type definitions for the sauna newsletter system."""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Annotated, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
import operator


class CandidateType(str, Enum):
    """Types of newsletter candidates."""
    EVENT = "event"
    NEWS = "news"
    OPENING = "opening"
    CLOSURE = "closure"
    OTHER = "other"


class Email(BaseModel):
    """Raw email metadata from Gmail."""
    id: str
    message_id: str
    sender: Optional[str] = None
    sender_name: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[datetime] = None
    raw_body: str
    processed_at: Optional[datetime] = None


class EmailArtifact(BaseModel):
    """LLM-compressed email content with sauna-relevance classification."""
    id: str
    email_id: str
    compressed_content: str
    summary: str
    is_sauna_related: bool = False
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    gemini_model: Optional[str] = None
    processed_at: Optional[datetime] = None


class SearchTheme(str, Enum):
    """Search themes for venue discovery."""
    EVENTS = "events"
    SESSIONS = "sessions"
    AUFGUSS = "aufguss"
    BANYA_NIGHTS = "banya nights"
    DJ_EVENTS = "dj events"
    WOMEN_ONLY = "women only"
    WORKSHOPS = "workshops"
    OPENINGS = "openings"
    COMING_SOON = "coming soon"
    NEW_LOCATION = "new location"
    POP_UP = "pop-up"
    CLOSURES = "closures"
    REFURB = "refurb"
    TEMP_CLOSED = "temporarily closed"
    GENERAL_NEWS = "london sauna news"


class Venue(BaseModel):
    """Represents a sauna venue from the watchlist."""
    name: str
    address: str
    description: str
    watchlist_ind: bool = False
    tags: List[str] = Field(default_factory=list)
    url: Optional[str] = None

    @classmethod
    def from_csv_row(cls, row: Dict[str, Any]) -> "Venue":
        """Create a Venue from a CSV row."""
        # Parse watchlist_ind safely (handle empty strings)
        watchlist_val = row.get("watchlist_ind", "")
        watchlist_ind = bool(int(watchlist_val)) if watchlist_val and watchlist_val.strip() else False

        # Parse tags safely
        tags_val = row.get("tags", "[]")
        try:
            tags = eval(tags_val) if isinstance(tags_val, str) and tags_val.strip() else []
        except:
            tags = []

        return cls(
            name=row.get("Name", ""),
            address=row.get("Address", ""),
            description=row.get("Description", ""),
            watchlist_ind=watchlist_ind,
            tags=tags,
            url=row.get("url")
        )


class SearchQuery(BaseModel):
    """A search query to be executed."""
    query: str
    theme: SearchTheme
    venue: Optional[str] = None
    context: Optional[str] = None


class PerplexityResult(BaseModel):
    """Result from a Perplexity search."""
    query: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    raw_response: Optional[Dict[str, Any]] = None


class BrowserUseResult(BaseModel):
    """Result from Browser Use event scraping."""
    venue_name: str
    venue_url: str
    success: bool
    events: Any  # Flexible structure from Browser Use agent
    error: Optional[str] = None


class Candidate(BaseModel):
    """A candidate item for the newsletter."""
    type: CandidateType
    title: str
    venue_match: str
    date: Optional[str] = None
    urls: List[str] = Field(default_factory=list)
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_query: Optional[str] = None
    source_type: Literal["web", "email", "scrape"] = "web"
    email_artifact_id: Optional[str] = None


class ReadingCornerArticle(BaseModel):
    """An article selected for the Reading Corner section."""
    title: str
    url: str
    source_publication: str
    published_date: Optional[str] = None
    summary: str  # 2-3 sentences explaining why it's interesting
    article_type: Literal["research", "cultural", "news"]


class NewsletterDraft(BaseModel):
    """A newsletter draft."""
    version: int = 1
    markdown_content: str
    issue_date: datetime
    sources: List[str] = Field(default_factory=list)
    candidates_used: List[Candidate] = Field(default_factory=list)
    critique: Optional[str] = None
    spotlight_venue: Optional[str] = None  # Name of venue featured in spotlight


class GraphState(TypedDict):
    """State for the LangGraph workflow with concurrent update support."""

    # Planning phase
    search_queries: List[SearchQuery]
    previous_issues: List[str]

    # Search phase (these can be updated concurrently by parallel nodes)
    perplexity_results: Annotated[List[PerplexityResult], operator.add]
    browser_use_results: Annotated[List[BrowserUseResult], operator.add]
    email_candidates: List[Candidate]

    # Deduplication phase
    candidates: List[Candidate]

    # Drafting phase
    draft: Optional[NewsletterDraft]
    critique: Optional[str]
    iteration_count: int
    max_iterations: int

    # Output phase
    notion_page_id: Optional[str]

    # Metadata
    run_id: str
    issue_date: datetime
    watchlist_venues: List[Venue]
    spotlight_venue: Optional[Venue]  # Venue selected for this week's spotlight
    spotlight_research: List[PerplexityResult]  # Research results about spotlight venue
    previous_spotlights: List[str]  # Venue names that have been spotlighted before

    # Reading Corner
    reading_corner_results: List[PerplexityResult]  # Search results for articles
    reading_corner_article: Optional[ReadingCornerArticle]  # Selected article
