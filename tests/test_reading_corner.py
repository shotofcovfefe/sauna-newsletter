#!/usr/bin/env python3
"""Quick test to verify reading corner integration."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all imports work."""
    print("Testing imports...")

    try:
        from src.models.types import ReadingCornerArticle, GraphState
        print("✓ ReadingCornerArticle model imported successfully")

        from src.workflows.gather_workflow import search_reading_corner_node
        print("✓ search_reading_corner_node imported successfully")

        from src.tools.draft_tools import draft_newsletter_content
        print("✓ draft_tools imports successfully")

        print("\n✓ All imports successful!")
        return True

    except Exception as e:
        print(f"\n✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_model_creation():
    """Test creating a ReadingCornerArticle model."""
    print("\nTesting model creation...")

    try:
        from src.models.types import ReadingCornerArticle

        article = ReadingCornerArticle(
            title="Test Article",
            url="https://example.com/article",
            source_publication="Test Publication",
            published_date="2026-01-30",
            summary="This is a test article about saunas.",
            article_type="news"
        )

        print(f"✓ Created article: {article.title}")
        print(f"  Source: {article.source_publication}")
        print(f"  Type: {article.article_type}")

        # Test serialization
        data = article.model_dump()
        print(f"✓ Serialized: {list(data.keys())}")

        return True

    except Exception as e:
        print(f"\n✗ Model creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Reading Corner Integration Test")
    print("=" * 60)
    print()

    success = True
    success &= test_imports()
    success &= test_model_creation()

    print()
    print("=" * 60)
    if success:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 60)

    sys.exit(0 if success else 1)
