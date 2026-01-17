"""Test MZScraper with updated 3-level logic"""
import asyncio
import sys
import logging
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import with package context
from src.scraper import MZScraper


async def test_scraper():
    scraper = MZScraper()

    # Test list_program_urls
    print("=== Testing list_program_urls() ===")
    urls = scraper.list_program_urls()
    print(f"\nFound {len(urls)} program URLs:")
    for i, url in enumerate(urls, 1):
        print(f"{i}. {url}")

    if urls:
        # Test extract_content on first URL
        print(f"\n=== Testing extract_content() on first URL ===")
        first_url = urls[0]
        print(f"URL: {first_url}\n")

        content = await scraper.extract_content(first_url, {})

        if content:
            print("✓ Content extracted successfully")
            print(f"  Title: {content.additional_metadata.get('title', 'N/A')}")
            print(f"  Description length: {len(content.description or '')}")
            print(f"  Summary length: {len(content.summary or '')}")
            print(f"  Documents: {len(content.documents)}")
            for i, doc in enumerate(content.documents[:3], 1):
                print(f"    {i}. {doc.title} ({doc.file_format})")
            print(f"  Funding: {content.funding_amounts}")
            print(f"  Deadline: {content.additional_metadata.get('deadline', 'N/A')}")
            print(f"  Eligibility: {content.eligible_recipients}")
            print(f"  Contact email: {content.contact_email}")
        else:
            print("✗ Failed to extract content")
    else:
        print("\n✗ No URLs found - check scraper logic")


if __name__ == '__main__':
    asyncio.run(test_scraper())
