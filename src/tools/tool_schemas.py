"""Tool schemas for Anthropic Claude SDK."""

from typing import List, Dict, Any

# Define tool schemas in Anthropic's format
TOOL_SCHEMAS = [
    {
        "name": "run_perplexity_searches",
        "description": "Run Perplexity searches for London sauna news and events. Returns search results with answers and citations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of search queries to execute"
                }
            },
            "required": ["search_queries"]
        }
    },
    {
        "name": "scrape_all_venues",
        "description": "Scrape events from all London sauna venues using the aggregator. Returns scraped events data.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "fetch_email_candidates",
        "description": "Fetch unused email artifacts from Supabase and convert to candidates. Returns email-sourced candidates from venue newsletters and mailing lists that haven't been used in previous newsletters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum confidence score (0.0-1.0) for sauna-relevance",
                    "default": 0.5
                }
            },
            "required": []
        }
    },
    {
        "name": "deduplicate_candidates",
        "description": "Deduplicate and extract structured candidates from search results, scraped events, and email candidates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "perplexity_results": {
                    "type": "array",
                    "description": "Results from Perplexity searches"
                },
                "scraped_events": {
                    "type": "array",
                    "description": "Events scraped from venue websites"
                },
                "watchlist_venues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of venue names to match against"
                },
                "email_candidates": {
                    "type": "array",
                    "description": "Optional list of email-sourced candidates to merge",
                    "default": []
                }
            },
            "required": ["perplexity_results", "scraped_events", "watchlist_venues"]
        }
    },
    {
        "name": "save_candidates",
        "description": "Save candidates to disk for future use. Returns save path and metadata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "description": "List of candidate dictionaries"
                },
                "run_id": {
                    "type": "string",
                    "description": "Optional run ID (defaults to timestamp)"
                }
            },
            "required": ["candidates"]
        }
    },
    {
        "name": "load_candidates",
        "description": "Load candidates from a saved run. Use 'latest' to get the most recent run.",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "Run ID to load, or 'latest' for most recent",
                    "default": "latest"
                }
            },
            "required": []
        }
    },
    {
        "name": "select_best_candidates",
        "description": "Use a lightweight model to select the most newsletter-worthy candidates. Reduces context by filtering weak candidates before drafting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "description": "Full list of candidates to filter"
                },
                "max_candidates": {
                    "type": "integer",
                    "description": "Maximum number of candidates to select",
                    "default": 15
                }
            },
            "required": ["candidates"]
        }
    },
    {
        "name": "load_previous_issues",
        "description": "Load previous newsletter issues from Notion for style reference.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of issues to retrieve",
                    "default": 3
                }
            },
            "required": []
        }
    },
    {
        "name": "draft_newsletter_content",
        "description": "Draft newsletter content using the house style and template. Saves draft to temp file and returns file path (NOT full content). If run_id is provided, loads spotlight venue data from the candidates JSON.",
        "input_schema": {
            "type": "object",
            "properties": {
                "shortlist": {
                    "type": "array",
                    "description": "List of selected candidates"
                },
                "previous_issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Previous newsletter issues for style reference"
                },
                "week_description": {
                    "type": "string",
                    "description": "Description of the target week"
                },
                "run_id": {
                    "type": "string",
                    "description": "Optional run ID to load spotlight venue data from candidates JSON"
                }
            },
            "required": ["shortlist", "previous_issues", "week_description"]
        }
    },
    {
        "name": "critique_newsletter",
        "description": "Critique the newsletter draft for quality, tone, and accuracy. Reads draft from file and returns verdict + critique file path (NOT full critique text).",
        "input_schema": {
            "type": "object",
            "properties": {
                "draft_file": {
                    "type": "string",
                    "description": "Path to draft file to critique"
                },
                "shortlist": {
                    "type": "array",
                    "description": "Candidates used in the draft"
                },
                "previous_issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Previous issues for comparison"
                }
            },
            "required": ["draft_file", "shortlist", "previous_issues"]
        }
    },
    {
        "name": "revise_newsletter_content",
        "description": "Revise the newsletter based on critique feedback. Reads draft and critique from files, saves revised draft to new file, returns file path (NOT full content).",
        "input_schema": {
            "type": "object",
            "properties": {
                "draft_file": {
                    "type": "string",
                    "description": "Path to current draft file"
                },
                "critique_file": {
                    "type": "string",
                    "description": "Path to critique file"
                },
                "shortlist": {
                    "type": "array",
                    "description": "Candidates to reference"
                }
            },
            "required": ["draft_file", "critique_file", "shortlist"]
        }
    },
    {
        "name": "publish_to_notion",
        "description": "Publish newsletter draft to Notion. Reads draft from file. Returns page ID and URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "draft_file": {
                    "type": "string",
                    "description": "Path to final draft file to publish"
                },
                "run_id": {
                    "type": "string",
                    "description": "Run identifier"
                },
                "issue_date": {
                    "type": "string",
                    "description": "Issue date (ISO format), defaults to today"
                }
            },
            "required": ["draft_file", "run_id"]
        }
    }
]
