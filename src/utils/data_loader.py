"""Utilities for loading venue data and previous issues."""

import csv
from pathlib import Path
from typing import List
from ..models.types import Venue


def load_watchlist() -> List[Venue]:
    """
    Load watchlist venues from the default CSV path.

    Returns:
        List of Venue objects with watchlist_ind=True
    """
    csv_path = Path(__file__).parent.parent.parent / "data" / "sauna_list_london_v2.csv"
    return load_watchlist_venues(str(csv_path))


def load_watchlist_venues(csv_path: str) -> List[Venue]:
    """
    Load watchlist venues from CSV.

    Args:
        csv_path: Path to the CSV file

    Returns:
        List of Venue objects with watchlist_ind=True
    """
    venues = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            venue = Venue.from_csv_row(row)
            if venue.watchlist_ind:
                venues.append(venue)

    return venues


def get_venue_names_and_aliases(venues: List[Venue]) -> List[str]:
    """
    Extract venue names and common aliases for matching.

    Args:
        venues: List of Venue objects

    Returns:
        List of venue names (primary names only for now)
    """
    return [v.name for v in venues]
