"""
Main entry point for MZe SZIF scraper.

Demonstrates autonomous scraping:
1. Register scraper
2. Run autonomous discovery and extraction
3. Export results to JSON
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from scrapers.grants.sources.registry import SubScraperRegistry
from scrapers.grants.sources.mze_szif_cz import MZeSZIFCzScraper


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)


async def main():
    """Main autonomous scraping workflow"""
    print("=" * 70)
    print("MZe SZIF National Grants Scraper - Autonomous Mode")
    print("=" * 70)
    print()

    # Create registry
    registry = SubScraperRegistry()

    # Register MZe scraper
    mze_scraper = MZeSZIFCzScraper()
    registry.register(mze_scraper)

    print(f"Registered scrapers: {registry.list_scrapers()}\n")

    # Run autonomous scraping
    print("Starting autonomous scrape...")
    print()

    all_grants = await mze_scraper.scrape_all_programs(year=2026)

    print()
    print("=" * 70)
    print(f"Scraping Complete: {len(all_grants)} grants extracted")
    print("=" * 70)
    print()

    # Show sample
    if all_grants:
        print("Sample grants:")
        for i, grant in enumerate(all_grants[:3], 1):
            print(f"\n{i}. {grant.additional_metadata.get('program_id', 'N/A')}: "
                  f"{grant.additional_metadata.get('program_name', 'N/A')}")
            print(f"   URL: {grant.source_url}")
            print(f"   Description: {grant.summary[:100] if grant.summary else 'N/A'}...")
            if grant.funding_amounts:
                print(f"   Funding: {grant.funding_amounts}")
            if grant.additional_metadata.get('deadline'):
                print(f"   Deadline: {grant.additional_metadata['deadline']}")
            print(f"   Documents: {len(grant.documents)}")
            print(f"   Eligibility: {', '.join(grant.eligible_recipients) if grant.eligible_recipients else 'N/A'}")

    # Export to JSON
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'mze_grants_{timestamp}.json'

    # Convert to dict
    grants_data = [grant.to_dict() for grant in all_grants]

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'source': 'MZe SZIF',
                'scraper': 'MZeSZIFCzScraper',
                'scraped_at': datetime.now().isoformat(),
                'total_grants': len(grants_data),
            },
            'grants': grants_data
        }, f, ensure_ascii=False, indent=2)

    print()
    print(f"Exported to: {output_file}")
    print()

    # Statistics
    with_funding = sum(1 for g in all_grants if g.funding_amounts)
    with_deadline = sum(1 for g in all_grants if g.additional_metadata.get('deadline'))
    with_documents = sum(1 for g in all_grants if g.documents)

    print("Statistics:")
    print(f"  Total grants: {len(all_grants)}")
    print(f"  With funding info: {with_funding}")
    print(f"  With deadline: {with_deadline}")
    print(f"  With documents: {with_documents}")


if __name__ == '__main__':
    asyncio.run(main())
