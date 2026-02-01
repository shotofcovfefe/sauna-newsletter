"""
Event filtering utilities to exclude high-frequency standard sessions.

This module identifies and filters out recurring standard sessions (hourly drop-ins,
regular classes) that shouldn't be featured in the newsletter, keeping only
special events worthy of coverage.
"""

from typing import List, Dict, Any
import re


# High-frequency patterns to exclude (standard hourly sessions)
EXCLUDE_PATTERNS = [
    # Arc Community - Standard sessions
    r"free\s*flow\s*\d+",  # Free Flow 70, Free Flow 50, etc.

    # Rebase Recovery - Standard classes
    r"member.?s.?suite",  # Matches member_s_suite, members_suite, etc.
    r"contrast.?immersion",
    r"urban.?oasis",
    r"prana.?flow",
    r"ladies.?only",
    r"mat.?pilates",
    r"dynamic.?flow",
    r"morning.?fix",

    # Community Sauna - Standard hourly bookings
    r"off[-\s]*peak\s*\d*h?\s*sauna",
    r"peak\s*\d+min\s*sauna",  # Peak 90min Sauna
    r"peak\s*\d+h\s*sauna",     # Peak 1h Sauna
    r"nhs\s*free\s*sauna",
    r"peak\s*time\s*\d*h?\s*sauna",
    r"\d+h?\s*sauna\s*session",
    r"members?\s*slot",         # Members Slot

    # WellNest - Standard recurring sessions (but keep special events)
    r"^breathwork,\s*saunas?\s*&\s*ice\s*baths?$",  # Exact match only, exclude specials
]

# Always include these patterns (special events)
ALWAYS_INCLUDE_PATTERNS = [
    r"workshop",
    r"special",
    r"birthday",
    r"ritual",
    r"ceremony",
    r"aufguss",
    r"banya",
    r"halloween",
    r"nye",
    r"new\s*year",
    r"galentine",
    r"valentine",
    r"solstice",
    r"equinox",
    r"full\s*moon",
    r"sound\s*bath",
    r"sound\s*healing",
    r"rewind\s*&\s*revive",  # WellNest special
    r"arc\s*after\s*dark",  # Arc special
    r"arc\s*birthday",
    r"mythic\s*sauna",
    r"sparkling\s*sauna",
    r"lange\s*saunanacht",
    r"rekindling",
    r"transient\s*radio",
]

# Venues that should be fully included (mostly special events)
ALWAYS_INCLUDE_VENUES = [
    "Sauna Social Club",
    "Sauna & Plunge",
    "Urban Heat Wellness",
    "SweSauna",  # Mostly special, some recurring Aufguss
]


def normalize_for_matching(text: str) -> str:
    """
    Normalize text for pattern matching.

    Args:
        text: Text to normalize

    Returns:
        Normalized lowercase text
    """
    return text.lower().strip()


def is_high_frequency_session(event_name: str, venue: str) -> bool:
    """
    Check if an event is a high-frequency standard session that should be excluded.

    Args:
        event_name: Name of the event
        venue: Venue name

    Returns:
        True if event should be excluded, False if it should be included
    """
    normalized_name = normalize_for_matching(event_name)

    # Always include events from special-event-only venues
    if venue in ALWAYS_INCLUDE_VENUES:
        return False

    # Check if event matches "always include" patterns (overrides exclude)
    for pattern in ALWAYS_INCLUDE_PATTERNS:
        if re.search(pattern, normalized_name, re.IGNORECASE):
            return False  # Don't exclude

    # Check if event matches exclude patterns
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, normalized_name, re.IGNORECASE):
            return True  # Exclude this event

    # Default: include the event
    return False


def filter_newsletter_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Filter events to exclude high-frequency standard sessions.

    Args:
        events: List of event dictionaries

    Returns:
        Dictionary with filtered events and statistics
    """
    included = []
    excluded = []

    for event in events:
        event_name = event.get('event_name', '')
        venue = event.get('venue', '')

        if is_high_frequency_session(event_name, venue):
            excluded.append(event)
        else:
            included.append(event)

    # Statistics by exclusion reason
    exclude_stats = {}
    for event in excluded:
        venue = event.get('venue', 'Unknown')
        if venue not in exclude_stats:
            exclude_stats[venue] = []
        exclude_stats[venue].append(event.get('event_name', 'Unknown'))

    return {
        'included': included,
        'excluded': excluded,
        'stats': {
            'total_input': len(events),
            'included_count': len(included),
            'excluded_count': len(excluded),
            'exclusion_rate': (len(excluded) / len(events) * 100) if events else 0,
            'excluded_by_venue': {
                venue: len(names)
                for venue, names in exclude_stats.items()
            }
        }
    }


def print_filter_stats(filter_result: Dict[str, Any]):
    """
    Print statistics about filtered events.

    Args:
        filter_result: Result from filter_newsletter_events()
    """
    stats = filter_result['stats']

    print("=" * 80)
    print("EVENT FILTERING RESULTS")
    print("=" * 80)
    print(f"Total events:      {stats['total_input']:>4}")
    print(f"Included (special):{stats['included_count']:>4} ({100 - stats['exclusion_rate']:.1f}%)")
    print(f"Excluded (standard):{stats['excluded_count']:>4} ({stats['exclusion_rate']:.1f}%)")
    print()

    if stats['excluded_by_venue']:
        print("Excluded by venue:")
        print("-" * 80)
        for venue, count in sorted(
            stats['excluded_by_venue'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            print(f"  {venue:<40} {count:>4} events")
    print()
