"""LangGraph workflow for newsletter generation."""

import uuid
from datetime import datetime
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from .models.types import GraphState
from .agents.search_agent import plan_search_queries, execute_searches
from .agents.dedup_agent import deduplicate_candidates, select_shortlist
from .agents.drafting_agent import (
    draft_newsletter,
    critique_draft,
    should_revise,
    revise_draft
)
from .agents.publish_agent import publish_to_notion
from .utils.data_loader import load_watchlist_venues
from .utils.date_utils import get_issue_date
from .services.notion_service import NotionService


def create_newsletter_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for newsletter generation.

    Workflow structure:
    1. Agentic Loop 1: Search & Selection
       - plan_queries → execute_searches → deduplicate → select_shortlist
    2. Agentic Loop 2: Drafting with Critique
       - draft → critique → [revise → critique]* → publish

    Returns:
        Compiled StateGraph
    """
    # Create workflow
    workflow = StateGraph(GraphState)

    # Add nodes
    # Loop 1: Search & Selection
    workflow.add_node("plan_queries", plan_search_queries)
    workflow.add_node("execute_searches", execute_searches)
    workflow.add_node("deduplicate", deduplicate_candidates)
    workflow.add_node("select_shortlist", select_shortlist)

    # Loop 2: Drafting
    workflow.add_node("draft", draft_newsletter)
    workflow.add_node("critique", critique_draft)
    workflow.add_node("revise", revise_draft)

    # Publishing
    workflow.add_node("publish", publish_to_notion)

    # Define edges
    # Loop 1 (linear)
    workflow.set_entry_point("plan_queries")
    workflow.add_edge("plan_queries", "execute_searches")
    workflow.add_edge("execute_searches", "deduplicate")
    workflow.add_edge("deduplicate", "select_shortlist")

    # Transition to Loop 2
    workflow.add_edge("select_shortlist", "draft")

    # Loop 2 (with conditional branching)
    workflow.add_edge("draft", "critique")
    workflow.add_conditional_edges(
        "critique",
        should_revise,
        {
            "revise": "revise",
            "publish": "publish"
        }
    )
    workflow.add_edge("revise", "critique")  # Loop back for another critique

    # End after publishing
    workflow.add_edge("publish", END)

    return workflow.compile()


def build_initial_state(
    watchlist_csv_path: str,
    previous_issues_limit: int = 5,
    max_iterations: int = 3
) -> GraphState:
    """
    Build the initial state for the workflow.

    Args:
        watchlist_csv_path: Path to watchlist CSV
        previous_issues_limit: Number of previous issues to retrieve
        max_iterations: Maximum drafting iterations

    Returns:
        Initial GraphState
    """
    # Load watchlist
    watchlist_venues = load_watchlist_venues(watchlist_csv_path)
    print(f"Loaded {len(watchlist_venues)} watchlist venues")

    # Retrieve previous issues
    notion = NotionService()
    previous_issues = notion.retrieve_previous_issues(limit=previous_issues_limit)
    print(f"Retrieved {len(previous_issues)} previous issues")

    # Get issue date
    issue_date = get_issue_date()
    print(f"Target issue date: {issue_date.strftime('%A, %B %d, %Y')}")

    # Create initial state
    state = GraphState(
        run_id=str(uuid.uuid4()),
        issue_date=issue_date,
        watchlist_venues=watchlist_venues,
        previous_issues=previous_issues,
        max_iterations=max_iterations
    )

    return state


def run_newsletter_workflow(
    watchlist_csv_path: str = "data/sauna_list_london_v3.csv",
    previous_issues_limit: int = 5,
    max_iterations: int = 3
) -> Dict[str, Any]:
    """
    Run the complete newsletter generation workflow.

    Args:
        watchlist_csv_path: Path to watchlist CSV
        previous_issues_limit: Number of previous issues to retrieve
        max_iterations: Maximum drafting iterations

    Returns:
        Final state and metadata
    """
    print("=" * 60)
    print("LONDON SAUNA NEWSLETTER - AGENTIC DRAFTING SYSTEM")
    print("=" * 60)
    print()

    # Build initial state
    initial_state = build_initial_state(
        watchlist_csv_path=watchlist_csv_path,
        previous_issues_limit=previous_issues_limit,
        max_iterations=max_iterations
    )

    # Create and run workflow
    workflow = create_newsletter_workflow()

    print()
    print("Starting workflow...")
    print()

    # Execute
    final_state = workflow.invoke(initial_state)

    print()
    print("=" * 60)
    print("WORKFLOW COMPLETE")
    print("=" * 60)
    print(f"Run ID: {final_state['run_id']}")
    print(f"Candidates found: {len(final_state['candidates'])}")
    print(f"Shortlist size: {len(final_state['shortlist'])}")
    print(f"Draft iterations: {final_state['iteration_count']}")
    print(f"Notion page ID: {final_state.get('notion_page_id', 'N/A')}")
    print()

    if final_state.get('draft'):
        print("Draft preview (first 500 chars):")
        print("-" * 60)
        print(final_state['draft'].markdown_content[:500])
        print("...")
        print("-" * 60)

    return final_state
