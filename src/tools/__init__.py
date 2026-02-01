"""Tool definitions for Claude SDK agent."""

from .gather_tools import (
    run_perplexity_searches,
    scrape_all_venues,
    fetch_email_candidates,
    deduplicate_candidates,
    save_candidates
)

from .draft_tools import (
    load_candidates,
    select_best_candidates,
    load_previous_issues,
    draft_newsletter_content,
    critique_newsletter,
    revise_newsletter_content
)

from .publish_tools import (
    publish_to_notion
)

__all__ = [
    # Gather tools
    "run_perplexity_searches",
    "scrape_all_venues",
    "fetch_email_candidates",
    "deduplicate_candidates",
    "save_candidates",

    # Draft tools
    "load_candidates",
    "select_best_candidates",
    "load_previous_issues",
    "draft_newsletter_content",
    "critique_newsletter",
    "revise_newsletter_content",

    # Publish tools
    "publish_to_notion"
]
