"""Simple test script for MZScraper without Apify Actor"""
import asyncio
import sys
sys.path.insert(0, '.')

from src.scraper import MZScraper


async def test_scraper():
    scraper = MZScraper()

    # Test list_program_urls
    print("Testing list_program_urls...")
    urls = scraper.list_program_urls()
    print(f"Found {len(urls)} program URLs:")
    for url in urls[:5]:  # Show first 5
        print(f"  - {url}")

    if urls:
        # Test extract_content on first URL
        print(f"\nTesting extract_content on first URL: {urls[0]}")
        content = await scraper.extract_content(urls[0], {})

        if content:
            print(f"\nExtracted content:")
            print(f"  - Title: {content.additional_metadata.get('title', 'N/A')}")
            print(f"  - Description length: {len(content.description or '')}")
            print(f"  - Documents: {len(content.documents)}")
            print(f"  - Funding: {content.funding_amounts}")
            print(f"  - Deadline: {content.additional_metadata.get('deadline', 'N/A')}")
            print(f"  - Eligibility: {content.eligible_recipients}")
        else:
            print("Failed to extract content")


if __name__ == '__main__':
    asyncio.run(test_scraper())
