"""
Test script for LLM extractor.

Usage:
    python test_llm_extractor.py          # Test standalone extractor
    python test_llm_extractor.py scraper  # Test integrated scraper
"""

import asyncio
import json
import sys
import requests
from bs4 import BeautifulSoup

from scrapers.grants.sources.llm_extractor import LLMExtractor


async def test_standalone_extraction():
    """Test the LLM extractor directly."""
    test_url = "https://opst.cz/dotace/101-vyzva/"

    print(f"Fetching: {test_url}")
    response = requests.get(test_url, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    for elem in soup.select("nav, footer, script, style, header"):
        elem.decompose()

    html_content = soup.get_text(" ", strip=True)
    print(f"Content length: {len(html_content)} chars\n")

    print("Running LLM extraction (basic + enhanced in parallel)...")
    extractor = LLMExtractor(model_name="anthropic/claude-haiku-4.5")

    basic, enhanced = await extractor.extract_full(
        html_content=html_content,
        page_url=test_url,
    )

    if basic:
        print("\n=== BASIC EXTRACTION ===\n")
        print(json.dumps(basic.model_dump(), indent=2, ensure_ascii=False))

    if enhanced:
        print("\n=== ENHANCED EXTRACTION ===\n")
        print(json.dumps(enhanced.model_dump(), indent=2, ensure_ascii=False))


async def test_integrated_scraper():
    """Test the OPST scraper with LLM enrichment enabled."""
    from scrapers.grants.sources.opst_cz import OPSTCzScraper

    test_url = "https://opst.cz/dotace/101-vyzva/"

    print(f"Testing integrated scraper with LLM enrichment")
    print(f"URL: {test_url}\n")

    # Create scraper with LLM enabled
    scraper = OPSTCzScraper(enable_llm=True)

    # Run extraction
    print("Running extract_content() with LLM enrichment...")
    content = await scraper.extract_content(
        url=test_url,
        grant_metadata={"title": "Test grant"},
    )

    if content:
        print("\n=== GRANT CONTENT ===\n")
        data = content.to_dict()
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        print("Extraction failed!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "scraper":
        asyncio.run(test_integrated_scraper())
    else:
        asyncio.run(test_standalone_extraction())
