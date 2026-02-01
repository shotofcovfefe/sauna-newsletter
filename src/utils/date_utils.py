"""Date utilities for newsletter scheduling."""

from datetime import datetime, timedelta
from typing import Tuple


def get_issue_date() -> datetime:
    """
    Get the issue date for the newsletter.

    Newsletter sends every Thursday morning (9-11am UK time).
    Draft should be ready Wednesday, one day prior.

    Returns:
    datetime for the upcoming Thursday
    """
    today = datetime.now()
    days_until_thursday = (3 - today.weekday()) % 7

    # If today is Thursday and it's before 11am, use today
    if days_until_thursday == 0 and today.hour < 11:
        return today.replace(hour=9, minute=0, second=0, microsecond=0)

    # Otherwise, get next Thursday
    if days_until_thursday == 0:
        days_until_thursday = 7

    next_thursday = today + timedelta(days=days_until_thursday)
    return next_thursday.replace(hour=9, minute=0, second=0, microsecond=0)


def get_event_date_range() -> Tuple[datetime, datetime]:
    """
    Get the date range for events to scrape.

    Events should be for Friday "this" week to Friday "next" week.

    Returns:
        Tuple of (start_date, end_date)
    """
    today = datetime.now()

    # Find this Friday
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0 and today.hour >= 12:
        # If it's Friday afternoon, start from next Friday
        days_until_friday = 7

    start_date = today + timedelta(days=days_until_friday)
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # End date is Friday of next week (7 days after start)
    end_date = start_date + timedelta(days=7)

    return start_date, end_date


def format_date_for_query(date: datetime) -> str:
    """Format a date for use in search queries."""
    return date.strftime("%B %d, %Y")  # e.g., "January 17, 2026"


def get_week_description() -> str:
    """Get a human-readable description of the target week."""
    start, end = get_event_date_range()
    return f"{start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"
