"""Tools for drafting newsletter content."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional



def load_candidates(run_id: str = "latest") -> Dict[str, Any]:
    """
    Load candidates from a saved run.

    Args:
        run_id: Run ID to load, or "latest" for most recent

    Returns:
        Dictionary with candidates and metadata
    """
    runs_dir = Path("data/runs")

    if run_id == "latest":
        # Find most recent run
        run_files = sorted(runs_dir.glob("*_candidates.json"), reverse=True)
        if not run_files:
            return {"error": "No candidate runs found"}
        input_file = run_files[0]
        run_id = input_file.stem.replace("_candidates", "")
    else:
        input_file = runs_dir / f"{run_id}_candidates.json"

    if not input_file.exists():
        return {"error": f"Candidates file not found: {input_file}"}

    with open(input_file, "r") as f:
        data = json.load(f)

    return {
        "run_id": run_id,
        "num_candidates": len(data.get("candidates", [])),
        "num_shortlist": len(data.get("shortlist", [])),
        "issue_date": data.get("issue_date"),
        "candidates": data.get("candidates", []),
        "shortlist": data.get("shortlist", [])
    }



def select_best_candidates(
    candidates: List[Dict],
    max_candidates: int = 15
) -> Dict[str, Any]:
    """
    Use a lightweight model to select the most newsletter-worthy candidates.

    This reduces context for the drafting step by filtering out weak candidates.

    Args:
        candidates: Full list of candidates from load_candidates
        max_candidates: Maximum number to select (default 15)

    Returns:
        Dictionary with selected candidates and metadata
    """
    import anthropic
    import os
    import json

    # Use Claude Haiku 4.5 for fast, cheap candidate selection
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Build selection prompt
    candidates_json = json.dumps(candidates, indent=2)

    system_prompt = """You are a newsletter curator for "London Sauna Briefing".

Your job is to select the MOST NEWSLETTER-WORTHY candidates from a list.

## SELECTION CRITERIA

**Prioritize**:
- NEW events, classes, or sessions (not recurring weekly sessions)
- Venue changes (openings, closures, renovations, policy changes)
- Special events (aufguss ceremonies, community gatherings, workshops)
- Interesting trends or cultural moments
- High-confidence candidates (confidence > 0.6)

**Deprioritize**:
- Regular weekly sessions that happen every week
- Vague or generic wellness content
- Low-confidence candidates (confidence < 0.4)
- Duplicate information across candidates

**Output format**: Return a JSON array of the selected candidates (unchanged objects from the input). Select the top {max_candidates} most interesting candidates.

Example output:
```json
[
  {{"type": "event", "title": "...", "venue": "...", ...}},
  {{"type": "class", "title": "...", "venue": "...", ...}}
]
```"""

    user_prompt = f"""Here are {len(candidates)} candidates. Select the top {max_candidates} most newsletter-worthy ones.

CANDIDATES:
{candidates_json}

Return ONLY the JSON array of selected candidates."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",  # Fast and cheap Haiku 4.5
            max_tokens=8000,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        response_text = message.content[0].text

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()

        selected = json.loads(json_str)

        return {
            "num_input": len(candidates),
            "num_selected": len(selected),
            "selected_candidates": selected,
            "status": "selection_complete"
        }

    except Exception as e:
        # Fallback: return top candidates by confidence
        print(f"Selection failed, using confidence fallback: {e}")
        sorted_candidates = sorted(
            candidates,
            key=lambda c: c.get("confidence", 0.5),
            reverse=True
        )
        selected = sorted_candidates[:max_candidates]

        return {
            "num_input": len(candidates),
            "num_selected": len(selected),
            "selected_candidates": selected,
            "status": "fallback_selection",
            "warning": f"LLM selection failed: {str(e)}"
        }


def load_previous_issues(limit: int = 3) -> Dict[str, Any]:
    """
    Load previous newsletter issues from Notion for style reference.

    Args:
        limit: Maximum number of issues to retrieve

    Returns:
        Dictionary with previous issues
    """
    try:
        from ..services.notion_service import NotionService

        notion = NotionService()
        previous_issues = notion.retrieve_previous_issues(limit=limit)

        return {
            "num_issues": len(previous_issues),
            "issues": previous_issues
        }
    except Exception as e:
        return {
            "num_issues": 0,
            "issues": [],
            "warning": f"Could not load previous issues: {str(e)}"
        }



def draft_newsletter_content(
    shortlist: List[Dict],
    previous_issues: List[str],
    week_description: str,
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Draft newsletter content using the house style and template.

    Args:
        shortlist: List of selected candidates
        previous_issues: Previous newsletter issues for style reference
        week_description: Description of the target week
        run_id: Run ID to load spotlight data from candidates JSON

    Returns:
        Dict with draft_file path and metadata (NOT the full content)
    """
    from ..agents.newsletter_template import NEWSLETTER_TEMPLATE, EXAMPLE_NEWSLETTER

    # Load the London sauna scene analysis for background context
    scene_analysis_path = Path(__file__).parent.parent.parent / "data" / "artifacts" / "london-sauna-scene-2025-2026.md"
    if scene_analysis_path.exists():
        with open(scene_analysis_path, "r") as f:
            scene_analysis = f.read()
    else:
        scene_analysis = ""

    # Build the drafting prompt with cacheable sections
    # The template and example are static and can be cached

    # Include scene analysis if available
    scene_context = ""
    if scene_analysis:
        scene_context = f"""
## BACKGROUND CONTEXT: THE LONDON SAUNA SCENE

You have access to comprehensive background analysis of the London sauna scene. Use this to:
- Understand venue typologies (Community Hub, High-Performance, Boutique, Mobile)
- Reference pricing ranges, operational models, and market positioning
- Draw on historical context and cultural trends when relevant
- Ground your analysis in the actual structure of the scene

**Important**: This is reference material. Don't quote it directly or sound academic. Use it to inform your observational writing and ensure factual accuracy about venues, pricing, and trends.

{scene_analysis[:8000]}

---
"""

    system_prompt_cacheable = f"""You are an expert newsletter writer for "London Sauna Briefing" - a sharp, opinionated insider newsletter.

{scene_context}

## CRITICAL RULES

1. **NO META-COMMENTARY**: Write the newsletter DIRECTLY. Do NOT say "I'm going to write...", "Here's a draft...", "Okay, I've revised...". START with the subject line immediately.

2. **VOICE & TONE**:
   - Sharp, factual, slightly contrarian
   - NO hype words ("ultimate", "must-see", "hawk-like")
   - NO cutesy phrases ("shall we say", "resist!")
   - NO emojis in body text (only in section headers where specified)
   - Write like explaining to a smart, skeptical friend
   - Confident but label uncertainty when present

3. **STRUCTURE IS MANDATORY**:
   Follow this exact structure:
   - Subject line (# LONDON SAUNA BRIEFING — [thesis])
   - Opening think-piece (3-6 paragraphs, point of view)
   - Sauna Scoreboard (optional if no data)
   - The Moves (3-5 bullets with ↑ ↓ NEW ⚠)
   - The Rankings (🥇 Best, 🥈/🥉 Secondary, 🐎 Dark Horse, optional ⚠ Caution)
   - The Weekend Windows (6-10 items grouped by day)
   - Optional: One Useful Idea, Sauna Culture Moment
   - The Ongoing Investigation
   - Close

4. **CONTENT RULES**:
   - Use the candidates provided, but ONLY if they're substantive
   - If candidates are thin/vague, be honest about limited info
   - Rankings > lists (make decisions, don't just describe)
   - Concrete > abstract ("venues adding quiet slots" not "wellness evolving")
   - If a section feels thin, CUT IT or acknowledge scarcity

5. **WHAT NOT TO DO**:
   - Don't pretend to have info you don't have
   - Don't write generic wellness advice
   - Don't make up venue names or events
   - Don't use previous issues to fake novelty

## TEMPLATE

{NEWSLETTER_TEMPLATE}

## EXAMPLE OF GOOD WRITING

{EXAMPLE_NEWSLETTER}

Study the example's tone, structure, and decisiveness. Match this style exactly."""

    # Format candidates
    candidates_text = "\n\n".join([
        f"[{i+1}] {c['type'].upper()}: {c['title']}\n"
        f"    Venue: {c.get('venue', 'unknown')}\n"
        f"    Date: {c.get('date', 'TBD')}\n"
        f"    Summary: {c.get('summary', '')}\n"
        f"    Confidence: {c.get('confidence', 0.5):.1f}/1.0\n"
        f"    URLs: {', '.join(c.get('urls', [])[:3])}"
        for i, c in enumerate(shortlist)
    ])

    # Handle previous issues
    if previous_issues and len(previous_issues) > 0:
        prev_context = f"""PREVIOUS ISSUE (for style/tone reference only):
{previous_issues[0][:2000]}..."""
    else:
        prev_context = """**NO PREVIOUS ISSUES** - This is an early issue. Don't claim to compare against previous newsletters that don't exist."""

    # Load spotlight data and reading corner article from JSON if run_id provided
    spotlight_context = ""
    reading_corner_context = ""
    if run_id:
        import json
        json_file = Path("data/runs") / f"{run_id}_candidates.json"

        if json_file.exists():
            with open(json_file, "r") as f:
                run_data = json.load(f)

            # Extract spotlight information if available
            if run_data.get("spotlight_venue") and run_data.get("spotlight_research"):
                spotlight_venue = run_data["spotlight_venue"]
                spotlight_research = run_data["spotlight_research"]

                spotlight_info = "\n\n".join([
                    f"**Query:** {r['query']}\n**Answer:** {r['answer']}"
                    for r in spotlight_research
                ])

                spotlight_context = f"""

**SPOTLIGHT VENUE THIS WEEK: {spotlight_venue}**

Research about this venue:
{spotlight_info}

Use this research to write a compelling venue spotlight section. This should be a deep dive on the venue - what makes it unique, who goes there, what the vibe is, pricing, location, history, etc.
"""

            # Extract reading corner article if available
            reading_corner_context = ""
            if run_data.get("reading_corner_article"):
                article = run_data["reading_corner_article"]
                reading_corner_context = f"""

**READING CORNER ARTICLE THIS WEEK:**

Title: {article['title']}
Source: {article['source_publication']}
URL: {article['url']}
Type: {article['article_type']}
{f"Published: {article['published_date']}" if article.get('published_date') else ""}

Why it's interesting: {article['summary']}

Write the "Reading Corner" section naturally. You can start with a brief intro line or go straight to the article - your choice. Vary the approach each week. Keep it 40-80 words total. Be direct, not chatty. Match the newsletter's sharp tone.
"""
            else:
                reading_corner_context = """

**NO READING CORNER THIS WEEK:**

No suitable article was found this week. OMIT the "Reading Corner" section entirely from the newsletter. Do not include it, do not mention it, just skip that section.
"""

    user_prompt = f"""TARGET WEEK: {week_description}

CANDIDATES FOR THIS WEEK ({len(shortlist)} items):

{candidates_text}

{spotlight_context}

{reading_corner_context}

{prev_context}

Write the newsletter now. Remember: NO meta-commentary. Start with the subject line."""

    # Use Claude to draft with prompt caching
    import anthropic
    import os

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Use Claude Opus 4.5 for high-quality drafting with prompt caching
    # This will be cached across calls, reducing costs by ~90% on subsequent calls
    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=4000,
        temperature=0.3,
        system=[
            {
                "type": "text",
                "text": system_prompt_cacheable,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )

    draft_content = message.content[0].text

    # Save draft to temp file to keep it OUT of orchestrator conversation
    from datetime import datetime

    temp_dir = Path("data/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    draft_file = temp_dir / f"draft_{timestamp}.md"

    with open(draft_file, "w") as f:
        f.write(draft_content)

    # Return lightweight metadata ONLY
    return {
        "draft_file": str(draft_file),
        "char_count": len(draft_content),
        "word_count": len(draft_content.split()),
        "preview": draft_content[:200] + "..." if len(draft_content) > 200 else draft_content,
        "status": "draft_created"
    }



def critique_newsletter(
    draft_file: str,
    shortlist: List[Dict],
    previous_issues: List[str]
) -> Dict[str, Any]:
    """
    Critique the newsletter draft for quality, tone, and accuracy.

    Args:
        draft_file: Path to draft file (NOT the content itself)
        shortlist: Candidates used in the draft
        previous_issues: Previous issues for comparison

    Returns:
        Dict with verdict and critique_file path (NOT full critique text)
    """
    # Read draft from file
    with open(draft_file, "r") as f:
        draft = f.read()
    system_prompt = """You are a sharp, demanding editor for "London Sauna Briefing".

Your job is to critique drafts and provide specific, actionable feedback.

## WHAT TO CHECK

1. **Tone violations**:
   - Hype words, cutesy language, unnecessary emojis
   - Vague claims without evidence
   - Generic wellness platitudes

2. **Structural issues**:
   - Missing required sections
   - Sections that feel thin or filler
   - Rankings that don't actually rank (no contrast)

3. **Factual concerns**:
   - Claims not supported by candidates
   - Made-up venue names or events
   - Pretending to have information not in the candidates

4. **Style issues**:
   - Meta-commentary ("I'm going to write...")
   - Lack of decisiveness (hedging too much)
   - Too bland or too aggressive

## OUTPUT FORMAT

Provide feedback in this format:

**MAJOR ISSUES** (blocking problems):
- [Issue 1]
- [Issue 2]

**MINOR IMPROVEMENTS**:
- [Issue 1]
- [Issue 2]

**VERDICT**: APPROVED / NEEDS REVISION

If APPROVED, say "APPROVED - ready to publish" (even if minor improvements noted).
If NEEDS REVISION, specify which sections need rework."""

    candidates_summary = "\n".join([
        f"- {c['title']} ({c.get('venue', 'unknown')})"
        for c in shortlist[:10]
    ])

    user_prompt = f"""DRAFT TO CRITIQUE:

{draft}

---

CANDIDATES USED:
{candidates_summary}

Provide your critique."""

    import anthropic
    import os

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Use Claude Sonnet 4.5 for critique (fast, smart, cheaper than Opus)
    # Use prompt caching for the static system prompt (critique guidelines)
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1500,
        temperature=0.2,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )

    critique = message.content[0].text

    # Save critique to file to keep it OUT of orchestrator conversation
    from datetime import datetime

    temp_dir = Path("data/temp")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    critique_file = temp_dir / f"critique_{timestamp}.txt"

    with open(critique_file, "w") as f:
        f.write(critique)

    # Determine verdict
    verdict = "APPROVED" if "APPROVED" in critique else "NEEDS_REVISION"

    # Extract key issues for orchestrator (lightweight summary)
    major_issues = []
    if "**MAJOR ISSUES**" in critique:
        issues_section = critique.split("**MAJOR ISSUES**")[1].split("**")[0]
        major_issues = [line.strip() for line in issues_section.split("-") if line.strip()][:3]

    # Return lightweight metadata ONLY
    return {
        "critique_file": str(critique_file),
        "verdict": verdict,
        "major_issues_summary": major_issues[:3] if major_issues else [],
        "char_count": len(critique)
    }



def revise_newsletter_content(
    draft_file: str,
    critique_file: str,
    shortlist: List[Dict]
) -> Dict[str, Any]:
    """
    Revise the newsletter based on critique feedback.

    Args:
        draft_file: Path to current draft file
        critique_file: Path to critique file
        shortlist: Candidates to reference

    Returns:
        Dict with revised_draft_file path (NOT full content)
    """
    # Read files
    with open(draft_file, "r") as f:
        draft = f.read()

    with open(critique_file, "r") as f:
        critique = f.read()
    system_prompt = """You are revising a newsletter draft based on editorial feedback.

## RULES

1. **NO META-COMMENTARY**: Don't say "I've revised..." or "Here's the updated version". Just output the revised newsletter.

2. **TARGETED EDITING**: Fix ONLY the specific issues mentioned in the critique. Don't rewrite sections that work.

3. **Preserve structure and working content**: Keep the same organizational structure, keep sections that weren't criticized.

4. **Surgical fixes**: If critique mentions "tone is too hype in section X", fix section X only. If "Rankings lack contrast", strengthen rankings only.

5. **Stay in character**: Maintain the sharp, opinionated house style.

6. **Start with the subject line**: Output the full revised newsletter with targeted edits applied."""

    user_prompt = f"""ORIGINAL DRAFT:

{draft}

---

CRITIQUE:

{critique}

---

Revise the newsletter to address the critique. Output the full revised newsletter."""

    import anthropic
    import os

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Use Claude Opus 4.5 for revision (high quality for final content)
    # Use prompt caching for the static system prompt (revision guidelines)
    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=4000,
        temperature=0.3,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )

    revised_content = message.content[0].text

    # Save revised draft to NEW file
    from datetime import datetime

    temp_dir = Path("data/temp")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    revised_draft_file = temp_dir / f"draft_{timestamp}_revised.md"

    with open(revised_draft_file, "w") as f:
        f.write(revised_content)

    # Return lightweight metadata ONLY
    return {
        "revised_draft_file": str(revised_draft_file),
        "char_count": len(revised_content),
        "word_count": len(revised_content.split()),
        "preview": revised_content[:200] + "..." if len(revised_content) > 200 else revised_content,
        "status": "revision_complete"
    }
