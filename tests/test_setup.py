#!/usr/bin/env python3
"""
Test script to validate the setup and API connections.

Run with: python test_setup.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def test_environment():
    """Test environment variables."""
    print("Testing environment variables...")

    load_dotenv()

    required_vars = [
        "PERPLEXITY_API_KEY",
        "GEMINI_API_KEY",
        "NOTION_API_KEY",
        "NOTION_DRAFT_NEWSLETTERS_DB_ID"
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
            print(f"  ✗ {var}: MISSING")
        else:
            # Mask the key
            masked = value[:8] + "..." if len(value) > 8 else "***"
            print(f"  ✓ {var}: {masked}")

    if missing:
        print(f"\n❌ Missing {len(missing)} required environment variable(s)")
        return False

    print("✓ All environment variables set\n")
    return True


def test_data_files():
    """Test data files."""
    print("Testing data files...")

    csv_path = "data/sauna_list_london_v2.csv"

    if not os.path.exists(csv_path):
        print(f"  ✗ {csv_path}: NOT FOUND")
        return False

    # Try to load it
    try:
        from src.utils.data_loader import load_watchlist_venues
        venues = load_watchlist_venues(csv_path)
        print(f"  ✓ {csv_path}: Found {len(venues)} watchlist venues")

        # Show a sample
        if venues:
            print(f"    Sample: {venues[0].name}")

    except Exception as e:
        print(f"  ✗ Error loading CSV: {e}")
        return False

    print("✓ Data files OK\n")
    return True


def test_perplexity():
    """Test Perplexity API connection."""
    print("Testing Perplexity API...")

    try:
        from src.services.perplexity_service import PerplexityService
        from src.models.types import SearchQuery, SearchTheme

        service = PerplexityService()

        # Simple test query
        query = SearchQuery(
            query="London sauna news this week",
            theme=SearchTheme.GENERAL_NEWS
        )

        result = service.search(query)

        if result.answer:
            print(f"  ✓ Perplexity API working")
            print(f"    Answer: {result.answer[:100]}...")
            print(f"    Sources: {len(result.sources)} URLs")
        else:
            print(f"  ✗ Empty response from Perplexity")
            return False

    except Exception as e:
        print(f"  ✗ Perplexity API error: {e}")
        return False

    print("✓ Perplexity API OK\n")
    return True


def test_gemini():
    """Test Gemini API connection."""
    print("Testing Gemini API...")

    try:
        from src.services.gemini_service import GeminiService

        service = GeminiService()

        # Simple test
        from langchain_core.messages import HumanMessage
        response = service.llm.invoke([HumanMessage(content="Say 'OK' if you can read this")])

        if response.content:
            print(f"  ✓ Gemini API working")
            print(f"    Response: {response.content[:100]}")
        else:
            print(f"  ✗ Empty response from Gemini")
            return False

    except Exception as e:
        print(f"  ✗ Gemini API error: {e}")
        return False

    print("✓ Gemini API OK\n")
    return True


def test_notion():
    """Test Notion API connection."""
    print("Testing Notion API...")

    try:
        from src.services.notion_service import NotionService

        service = NotionService()

        # Try to query the database
        response = service.client.databases.retrieve(service.database_id)

        if response:
            print(f"  ✓ Notion API working")
            print(f"    Database: {response.get('title', [{}])[0].get('plain_text', 'Unknown')}")
        else:
            print(f"  ✗ Could not retrieve database")
            return False

    except Exception as e:
        print(f"  ✗ Notion API error: {e}")
        return False

    print("✓ Notion API OK\n")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("SETUP VALIDATION")
    print("=" * 60)
    print()

    tests = [
        ("Environment", test_environment),
        ("Data Files", test_data_files),
        ("Perplexity", test_perplexity),
        ("Gemini", test_gemini),
        ("Notion", test_notion)
    ]

    results = {}

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"❌ {name} test failed with exception: {e}\n")
            results[name] = False

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print()
    print(f"Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All tests passed! You're ready to run the workflow.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
