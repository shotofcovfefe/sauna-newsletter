# London Sauna Newsletter - Agentic Drafting System

An agentic system for automatically researching, curating, and drafting a weekly London sauna newsletter.

## Overview

This system uses:
- **Perplexity API** for web search and discovery
- **Gemini Flash** (gemini-2.0-flash-exp) for deduplication, selection, and drafting
- **LangGraph** for orchestrating two agentic loops
- **Notion API** for publishing markdown drafts (review/archive)

## Architecture

The system uses **two distinct workflows** for better control and context isolation:

### Workflow 1: Gather (Deterministic LangGraph)
1. **Load watchlist**: Load venue list from CSV
2. **Scrape venues**: Scrape events from venue websites (Arc, Community Sauna, Rebase, etc.)
3. **Fetch emails**: Query Supabase for unused email artifacts from venue newsletters
4. **Search news**: Run predefined Perplexity searches for London sauna news
5. **Deduplicate**: Extract and merge candidates from all sources using Gemini Flash
6. **Save**: Persist candidates to `data/runs/{run_id}_candidates.json`

### Workflow 2: Draft (Agentic LangGraph)
1. **Load**: Read candidates from saved run
2. **Select**: Choose ~15 best items using Gemini
3. **Draft**: Generate opinionated newsletter using Gemini Flash
4. **Critique**: Analyze draft for novelty, clarity, length, and tone issues
5. **Revise**: Apply fixes (max 2-3 iterations)
6. **Publish**: Create Notion page (markdown)
7. **Track**: Mark email artifacts as used in Supabase

**Why separate workflows?**
- **Gather is deterministic** (fast, cheap, predictable) - no LLM decisions about what to scrape
- **Draft is agentic** (smart, creative) - uses LLM for editorial judgment
- Better context isolation (avoids token limit issues)
- Allows human review of candidates before drafting
- Can re-draft from same candidates without re-searching
- More flexible scheduling options

## Setup

1. **Clone the repository**
   ```bash
   cd sauna-newsletter
   ```

2. **Install dependencies**

   Using uv (recommended):
   ```bash
   uv sync
   ```

   Or using pip:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**

   Make sure your `.env` file contains:
   ```
   # Required for gathering
   PERPLEXITY_API_KEY=your_key_here
   GEMINI_API_KEY=your_key_here

   # Required for drafting & publishing
   NOTION_API_KEY=your_key_here
   NOTION_DRAFT_NEWSLETTERS_DB_ID=your_db_id_here

   # Optional: Email integration (for venue newsletter candidates)
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   ```

4. **Prepare watchlist data**

   Ensure `data/sauna_list_london_v2.csv` exists with `watchlist_ind=1` for core venues.

## Usage

The system has **two separate workflows** that can be run independently:

### 1. Gather Workflow (Deterministic LangGraph)

Collects candidates from all sources using a **deterministic workflow** (no agentic decisions):

```bash
python gather.py
```

This will:
- Load the watchlist venues
- Scrape events from all venue websites
- Fetch unused email candidates from Supabase (if configured)
- Run predefined Perplexity searches for news
- Deduplicate and merge all sources using Gemini
- Save candidates to `data/runs/{run_id}_candidates.json`

**Note**: Email candidates are automatically included if Supabase is configured. If not, they're gracefully skipped.

### 2. Draft Workflow (Agentic LangGraph)

Loads candidates and drafts the newsletter using an **agentic workflow** (LLM makes editorial decisions):

```bash
python draft.py --run-id latest
# or
python draft.py --run-id 20260111_153045
```

This will:
- Load candidates from the specified run
- Select best candidates using Gemini
- Draft newsletter using house style template
- Critique the draft for quality/tone
- Revise if needed (max 3 iterations)
- Publish to Notion as draft
- **Mark email artifacts as used** (prevents duplication across newsletters)

### Combined Workflow (Optional)

Run both workflows in sequence:

```bash
python main.py              # Run both workflows
python main.py --gather     # Run gather only
python main.py --draft      # Run draft only (uses latest)
```

### List Available Runs

```bash
python draft.py --list
```

### Output

The gather workflow saves candidates to `data/runs/{run_id}_candidates.json`.

The draft workflow creates a **Notion page** with:
- **Properties**: Issue Date, Status="Draft", Run ID
- **Content**: Newsletter markdown rendered as Notion blocks
- **Sources**: URLs from all candidates

## Project Structure

```
sauna-newsletter/
├── src/
│   ├── agents/          # LangGraph agents (search, dedup, drafting, publish)
│   ├── models/          # Pydantic data models
│   ├── services/        # External API integrations (Perplexity, Gemini, Notion)
│   ├── workflows/       # Gather and Draft workflows
│   └── utils/           # Data loading and date utilities
├── data/
│   ├── runs/            # Saved candidate runs (JSON)
│   └── sauna_list_london_v2.csv  # Watchlist venues
├── gather.py            # Gather workflow CLI
├── draft.py             # Draft workflow CLI
├── main.py              # Combined workflow (optional)
├── test_setup.py        # Setup validation script
├── pyproject.toml       # Project dependencies (uv)
├── uv.lock              # Locked dependencies
├── requirements.txt     # Dependencies (legacy pip)
└── .env                 # API keys (not committed)
```

## Scheduling

The newsletter is designed to send every **Thursday morning (9-11am UK time)**.

- Draft should be ready **Wednesday** (one day prior)
- Events are scraped for **Friday this week to Friday next week**

You can schedule the workflows with cron or a task scheduler:

### Option 1: Combined workflow
```bash
# Run both workflows every Wednesday at 6pm
0 18 * * 3 cd /path/to/sauna-newsletter && python main.py
```

### Option 2: Separate workflows (recommended)
```bash
# Gather candidates on Wednesday at 3pm
0 15 * * 3 cd /path/to/sauna-newsletter && python gather.py

# Draft and publish on Wednesday at 6pm (allows manual review of candidates)
0 18 * * 3 cd /path/to/sauna-newsletter && python draft.py --run-id latest
```

## Customization

### Adjust search themes
Edit `src/models/types.py` → `SearchTheme` enum

### Modify newsletter template
Edit `src/agents/drafting_agent.py` → `NEWSLETTER_TEMPLATE`

### Change iteration limits
Pass `max_iterations` parameter to `run_newsletter_workflow()`

### Adjust shortlist size
Edit `src/agents/dedup_agent.py` → `select_shortlist()` → `target_count`

## Notes

- The system isolates context to avoid token limit issues
- Previous issues are sampled (not all loaded) to reduce context size
- Search queries are capped at 5 concurrent requests to Perplexity
- Gemini Flash is used for all LLM operations (dedup, selection, drafting, critique)

## License

MIT
