"""Publishing agent for Notion integration."""

from ..models.types import GraphState
from ..services.notion_service import NotionService


def publish_to_notion(state: GraphState) -> GraphState:
    """
    Publish the final draft to Notion.

    Args:
        state: Current graph state

    Returns:
        Updated state with notion_page_id
    """
    if not state["draft"]:
        print("⚠ No draft to publish")
        return state

    # Publish to Notion
    notion = NotionService()
    page_id = notion.create_draft_page(
        draft=state["draft"],
        run_id=state["run_id"]
    )
    state["notion_page_id"] = page_id
    print(f"✓ Published to Notion: {page_id}")

    return state
