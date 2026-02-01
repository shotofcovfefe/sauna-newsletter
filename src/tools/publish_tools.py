"""Tools for publishing newsletter drafts."""

import os
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
import json



def publish_to_notion(
    draft_file: str,
    run_id: str,
    issue_date: str = None
) -> Dict[str, Any]:
    """
    Publish newsletter draft to Notion.

    Args:
        draft_file: Path to draft markdown file (NOT the content)
        run_id: Run identifier
        issue_date: Issue date (ISO format), defaults to today

    Returns:
        Dictionary with Notion page ID and URL
    """
    # Read draft from file
    with open(draft_file, "r") as f:
        draft_content = f.read()
    from ..services.notion_service import NotionService
    from ..models.types import NewsletterDraft

    if not issue_date:
        issue_date = datetime.now().isoformat()

    # Save draft locally before publishing
    output_dir = Path("data/drafts")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save markdown
    markdown_file = output_dir / f"{run_id}_draft.md"
    with open(markdown_file, "w") as f:
        f.write(draft_content)

    # Save metadata
    metadata_file = output_dir / f"{run_id}_draft_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump({
            "run_id": run_id,
            "issue_date": issue_date,
            "created_at": datetime.now().isoformat(),
            "markdown_file": str(markdown_file),
            "content_length": len(draft_content)
        }, f, indent=2)

    # Create draft object
    draft = NewsletterDraft(
        markdown_content=draft_content,
        issue_date=datetime.fromisoformat(issue_date.split('T')[0]),
        sources=[],  # Will be populated if needed
        version=1
    )

    # Publish to Notion
    notion = NotionService()
    page_id = notion.create_draft_page(draft=draft, run_id=run_id)

    # Mark email artifacts as used (if any)
    _mark_email_artifacts_used(run_id)

    return {
        "notion_page_id": page_id,
        "notion_url": f"https://notion.so/{page_id}",
        "status": "draft_created_in_notion",
        "notion_status": "Draft",
        "local_markdown_file": str(markdown_file),
        "local_metadata_file": str(metadata_file)
    }


def _mark_email_artifacts_used(run_id: str) -> None:
    """
    Mark email artifacts as used in a newsletter run.

    Loads candidates from the run file and marks any email-sourced
    candidates as used in Supabase.

    Args:
        run_id: Newsletter run identifier
    """
    # Check if Supabase is configured
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        # Supabase not configured, skip silently
        return

    try:
        # Load candidates from run file
        candidates_file = Path("data/runs") / f"{run_id}_candidates.json"
        if not candidates_file.exists():
            print(f"Warning: Candidates file not found for run {run_id}")
            return

        with open(candidates_file, "r") as f:
            data = json.load(f)

        # Extract email artifact IDs
        email_artifact_ids = []
        for candidate in data.get("candidates", []):
            if (candidate.get("source_type") == "email" and
                candidate.get("email_artifact_id")):
                email_artifact_ids.append(candidate["email_artifact_id"])

        if not email_artifact_ids:
            # No email candidates in this run
            return

        # Mark artifacts as used
        from supabase import create_client
        from ..services.email_processor_service import EmailProcessorService

        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

        processor = EmailProcessorService(
            supabase_client=supabase,
            gemini_api_key=os.getenv("GEMINI_API_KEY")
        )

        processor.mark_artifacts_used(email_artifact_ids, run_id)
        print(f"✓ Marked {len(email_artifact_ids)} email artifacts as used in newsletter {run_id}")

    except Exception as e:
        print(f"Warning: Failed to mark email artifacts as used: {e}")
        # Don't fail the publish if this step fails


