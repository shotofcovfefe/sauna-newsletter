"""Claude SDK orchestrator for newsletter workflow."""

import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import anthropic


class NewsletterOrchestrator:
    """
    Main orchestrator for newsletter generation using Claude SDK.

    This class creates a Claude agent that:
    1. Gathers candidates (if needed)
    2. Drafts newsletter using house style
    3. Critiques and revises (iterative loop)
    4. Publishes to Notion
    """

    def __init__(self):
        """Initialize the orchestrator with Claude client."""
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Load tool schemas
        from ..tools.tool_schemas import TOOL_SCHEMAS
        self.tool_schemas = TOOL_SCHEMAS

        # Load tool functions
        from ..tools import (
            run_perplexity_searches,
            scrape_all_venues,
            fetch_email_candidates,
            deduplicate_candidates,
            save_candidates,
            load_candidates,
            select_best_candidates,
            load_previous_issues,
            draft_newsletter_content,
            critique_newsletter,
            revise_newsletter_content,
            publish_to_notion
        )

        # Map tool names to functions
        self.tool_functions = {
            "run_perplexity_searches": run_perplexity_searches,
            "scrape_all_venues": scrape_all_venues,
            "fetch_email_candidates": fetch_email_candidates,
            "deduplicate_candidates": deduplicate_candidates,
            "save_candidates": save_candidates,
            "load_candidates": load_candidates,
            "select_best_candidates": select_best_candidates,
            "load_previous_issues": load_previous_issues,
            "draft_newsletter_content": draft_newsletter_content,
            "critique_newsletter": critique_newsletter,
            "revise_newsletter_content": revise_newsletter_content,
            "publish_to_notion": publish_to_notion
        }

    def run(
        self,
        mode: str = "full",
        run_id: Optional[str] = "latest",
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Run the newsletter workflow.

        Args:
            mode: "full" (gather + draft), "draft-only" (skip gathering), or "gather-only"
            run_id: Run ID to use for drafting (if mode != "full")
            max_iterations: Maximum draft iterations

        Returns:
            Dictionary with results
        """
        # Build system prompt
        system_prompt = self._build_system_prompt(mode, max_iterations)

        # Build user prompt
        user_prompt = self._build_user_prompt(mode, run_id)

        # Create conversation
        messages = [{"role": "user", "content": user_prompt}]

        print("=" * 70)
        print("LONDON SAUNA NEWSLETTER - CLAUDE ORCHESTRATOR")
        print("=" * 70)
        print(f"Mode: {mode}")
        print(f"Max iterations: {max_iterations}")
        print()

        # Agentic loop
        iteration = 0
        max_loop_iterations = 10  # Safety limit to prevent runaway loops

        while iteration < max_loop_iterations:
            print(f"\n[Iteration {iteration + 1}]")

            # Call Claude Sonnet 4.5 with tools (fast, smart orchestrator)
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=self.tool_schemas
            )

            # Check if done
            if response.stop_reason == "end_turn":
                # Extract final response
                final_text = ""
                for block in response.content:
                    if block.type == "text":
                        final_text += block.text

                print("\n" + "=" * 70)
                print("WORKFLOW COMPLETE")
                print("=" * 70)
                print(final_text)

                return {
                    "status": "success",
                    "final_message": final_text,
                    "iterations": iteration + 1
                }

            # Process tool calls
            if response.stop_reason == "tool_use":
                # Add assistant message to conversation
                messages.append({"role": "assistant", "content": response.content})

                # Execute tools
                tool_results = []
                last_tool_name = None
                for block in response.content:
                    if block.type == "tool_use":
                        last_tool_name = block.name
                        result = self._execute_tool(block)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result)
                        })

                # Add tool results to conversation
                messages.append({"role": "user", "content": tool_results})

            iteration += 1

        # Safety exit
        return {
            "status": "max_iterations_reached",
            "message": "Workflow did not complete within iteration limit",
            "iterations": iteration
        }

    def _build_system_prompt(self, mode: str, max_iterations: int) -> str:
        """Build the system prompt for the orchestrator."""
        from ..agents.london_sauna_context import LONDON_SAUNA_SCENE_CONTEXT, PRIORITY_VENUES, SEARCH_THEMES

        return f"""You are the orchestrator for "London Sauna Briefing" - an opinionated weekly newsletter.

{LONDON_SAUNA_SCENE_CONTEXT}

## YOUR WORKFLOW

Mode: {mode}

{self._get_workflow_instructions(mode)}

## AVAILABLE TOOLS

You have access to these tools:

**Gathering:**
- run_perplexity_searches: Search for London sauna news/events
- scrape_all_venues: Scrape events from venue websites
- fetch_email_candidates: Fetch unused email artifacts from Supabase
- deduplicate_candidates: Extract and deduplicate candidates (merges all sources)
- save_candidates: Save candidates to disk

**Drafting:**
- load_candidates: Load saved candidates
- select_best_candidates: Filter to most newsletter-worthy candidates (uses Haiku for efficiency)
- load_previous_issues: Load previous newsletters for style reference
- draft_newsletter_content: Draft the newsletter
- critique_newsletter: Critique the draft
- revise_newsletter_content: Revise based on critique (max {max_iterations} iterations)

**Publishing:**
- publish_to_notion: Publish to Notion (markdown)

## DECISION MAKING

- **Use tools sequentially** - wait for results before deciding next step
- **Check if candidates exist** before gathering
- **ALWAYS use select_best_candidates** after loading candidates (reduces context by 50-70%)
- **Draft → Critique → Revise loop** (max {max_iterations} times)
- **Stop revising** if critique says "APPROVED"
- **Publish to Notion** when done

## OUTPUT

When finished, provide a summary of what was accomplished."""

    def _get_workflow_instructions(self, mode: str) -> str:
        """Get workflow instructions based on mode."""
        from ..agents.london_sauna_context import PRIORITY_VENUES, SEARCH_THEMES

        if mode == "full":
            return """
**FULL WORKFLOW:**

1. **Check for existing candidates**: Use load_candidates with run_id="latest"
   - If found and recent (< 7 days old), ask if you should reuse or re-gather
   - If not found or old, proceed to gathering

2. **Gather candidates** (if needed):
   - Generate search queries for London sauna news/events
   - Run Perplexity searches
   - Scrape all venue websites
   - Fetch email candidates from Supabase (if configured)
   - Deduplicate and extract structured candidates (merges all sources)
   - Save candidates with timestamp

3. **Draft newsletter**:
   - Load candidates
   - Select best candidates using select_best_candidates (reduces context)
   - Load previous issues
   - Draft using the house style (sharp, opinionated, no hype)
   - Follow the template structure exactly

4. **Critique and revise**:
   - Critique the draft
   - If "APPROVED", proceed to publish
   - If "NEEDS REVISION", revise and critique again (max 3 iterations)

5. **Publish**:
   - Publish to Notion
   - Report URL and status
"""
        elif mode == "draft-only":
            return """
**DRAFT-ONLY WORKFLOW:**

1. **Load candidates**: Use the specified run_id
2. **Load previous issues**: For style reference
3. **Draft newsletter**: Use house style and template (use ALL candidates, don't filter)
4. **Critique and revise**: Iterative loop (max 3 times)
5. **Publish**: To Notion

NOTE: Do NOT use select_best_candidates - use all candidates directly for drafting.
"""
        elif mode == "gather-only":
            return f"""
**GATHER-ONLY WORKFLOW:**

1. **Generate search queries** for London sauna scene
   - Focus on priority venues: {', '.join(PRIORITY_VENUES[:8])}
   - Include themes: quiet sessions, aufguss, new openings, closures, community events
   - Search for CHANGES (not just ongoing sessions)
   - Add sentiment search: "London sauna scene vibe 2026", "sauna trends London"

2. **Run Perplexity searches**
3. **Scrape venue websites**
4. **Fetch email candidates** from Supabase (if configured - gracefully skip if not available)
5. **Deduplicate and extract candidates** (focus on CHANGES and EVENTS, merge all sources including emails)
6. **Save to disk** with timestamp
7. **Report** how many candidates were found (including breakdown by source)

Suggested themes: {', '.join(SEARCH_THEMES[:5])}
"""
        else:
            return f"Unknown mode: {mode}"

    def _build_user_prompt(self, mode: str, run_id: str) -> str:
        """Build the user prompt."""
        today = datetime.now().strftime("%A, %B %d, %Y")

        if mode == "full":
            return f"""Today is {today}.

Please run the full newsletter workflow:
1. Check for existing candidates (and decide if we need to re-gather)
2. Gather candidates if needed
3. Draft the newsletter
4. Critique and revise
5. Publish to Notion

Target week: This coming weekend (Friday - Sunday).

Begin the workflow now."""

        elif mode == "draft-only":
            return f"""Today is {today}.

Please draft the newsletter using candidates from run: {run_id}

Steps:
1. Load candidates from {run_id}
2. Load previous issues for style reference
3. Draft the newsletter using ALL candidates (pass run_id="{run_id}" to draft_newsletter_content to load spotlight venue data)
4. Critique and revise (iterate if needed)
5. Publish to Notion

IMPORTANT: Do NOT use select_best_candidates. Pass all candidates directly to draft_newsletter_content.

Begin now."""

        elif mode == "gather-only":
            return f"""Today is {today}.

Please gather candidates for this weekend's newsletter:
1. Generate search queries for London sauna news/events
2. Run Perplexity searches
3. Scrape venue websites
4. Fetch email candidates (if Supabase is configured)
5. Deduplicate and extract candidates from all sources
6. Save to disk

Target week: This coming weekend (Friday - Sunday).

Begin gathering now."""

        else:
            return f"Run the workflow in mode: {mode}"

    def _execute_tool(self, tool_use) -> Any:
        """Execute a tool and return the result."""
        tool_name = tool_use.name
        tool_input = tool_use.input

        print(f"  → Executing: {tool_name}({list(tool_input.keys())})")

        if tool_name not in self.tool_functions:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            # Execute the tool
            tool_func = self.tool_functions[tool_name]
            result = tool_func(**tool_input)

            print(f"  ✓ Result: {str(result)[:200]}...")
            return result

        except Exception as e:
            error_msg = f"Error executing {tool_name}: {str(e)}"
            print(f"  ✗ {error_msg}")
            import traceback
            traceback.print_exc()
            return {"error": error_msg}
