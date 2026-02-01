#!/usr/bin/env python3
"""
Test script to verify Gemini API integration works correctly.

This script tests the email compression and classification WITHOUT:
- Touching the database
- Requiring Gmail credentials
- Creating any persistent data

Usage:
    python src/scripts/test_gemini_integration.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_gemini_import():
    """Test that we can import the new Google GenAI SDK."""
    print("Testing Google GenAI SDK import...")
    try:
        from google import genai
        print("✓ Successfully imported google.genai")
        return True
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        print("\nRun: pip install google-genai")
        return False


def test_gemini_client():
    """Test that we can initialize Gemini client."""
    print("\nTesting Gemini client initialization...")

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("✗ GEMINI_API_KEY not found in environment")
        return False

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        print("✓ Successfully initialized Gemini client")
        return client
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return False


def test_generate_content(client):
    """Test basic content generation."""
    print("\nTesting content generation...")

    test_prompt = "Say 'Hello, this is a test' and nothing else."

    try:
        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=test_prompt
        )
        print(f"✓ Response received: {response.text[:100]}")
        return True
    except Exception as e:
        print(f"✗ Failed to generate content: {e}")
        print(f"\nError details: {type(e).__name__}")
        return False


def test_email_compression(client):
    """Test email compression logic."""
    print("\nTesting email compression...")

    sample_email = """
    Dear Customer,

    Join us for our AMAZING SAUNA EVENT on February 14th!

    What: Valentine's Day Sauna Session
    When: February 14, 2026, 7-9pm
    Where: London Sauna Club, 123 Test Street
    Price: £25

    Book now at https://example.com/book

    [Lots of marketing fluff and images here]
    """

    prompt = f"""You are an email content extractor for a London sauna newsletter.

Extract the key points from emails, focusing on:
- Events (dates, times, locations, names)
- News and announcements
- Openings, closures, or changes
- Special offers or promotions

Remove all:
- HTML formatting and tags
- Image references and graphics
- Excessive whitespace
- Marketing fluff and boilerplate

Summarize in 3-7 concise bullet points. Be specific about dates, times, and venue names if mentioned.

Email content:
{sample_email}"""

    try:
        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=prompt
        )
        compressed = response.text.strip()
        print(f"✓ Compressed content:\n{compressed}")
        return True
    except Exception as e:
        print(f"✗ Failed to compress email: {e}")
        return False


def test_classification(client):
    """Test sauna relevance classification."""
    print("\nTesting sauna relevance classification...")

    test_cases = [
        ("Sauna event this weekend!", "Join us for a sauna session on Saturday"),
        ("Software update", "Your Adobe subscription is expiring"),
    ]

    for subject, content in test_cases:
        prompt = f"""You are a content classifier for a London sauna newsletter.

Analyze emails to determine if they're related to saunas, wellness, or spa/thermal bathing in London.

Respond in this exact format:
RELEVANT: yes/no
CONFIDENCE: 0.0-1.0
SUMMARY: One-line summary of the email content

Rules:
- Mark as relevant if it mentions: saunas, spas, thermal bathing, wellness events, bathhouses, steam rooms
- Mark as NOT relevant if it's: promotions for unrelated businesses, newsletters about other topics
- Confidence should be high (0.8+) for explicit sauna mentions, medium (0.5-0.7) for general wellness, low (0.3-0.4) for tangential

Subject: {subject}

Content:
{content}"""

        try:
            response = client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=prompt
            )
            result = response.text.strip()
            print(f"\nTest case: '{subject}'")
            print(f"Result:\n{result}")
        except Exception as e:
            print(f"✗ Failed classification for '{subject}': {e}")
            return False

    print("\n✓ Classification tests completed")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Gemini Integration Test Suite")
    print("=" * 60)
    print()

    # Test 1: Import
    if not test_gemini_import():
        sys.exit(1)

    # Test 2: Client initialization
    client = test_gemini_client()
    if not client:
        sys.exit(1)

    # Test 3: Basic generation
    if not test_generate_content(client):
        sys.exit(1)

    # Test 4: Email compression
    if not test_email_compression(client):
        sys.exit(1)

    # Test 5: Classification
    if not test_classification(client):
        sys.exit(1)

    print()
    print("=" * 60)
    print("All Tests Passed!")
    print("=" * 60)
    print()
    print("The Gemini integration is working correctly.")
    print("You can now run: python src/scripts/scrape_emails.py")
    print()


if __name__ == "__main__":
    main()
