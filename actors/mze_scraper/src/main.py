"""
Apify Actor entry point for MZe SZIF National Grants Scraper.

This actor autonomously scrapes Czech Ministry of Agriculture national grants
from szif.gov.cz, extracting funding amounts, deadlines, eligibility criteria,
and documents.
"""

import asyncio
import logging
from apify import Actor

# Import from parent directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.grants.sources.registry import SubScraperRegistry
from scrapers.grants.sources.mze_szif_cz import MZeSZIFCzScraper


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)


async def main():
    """Main Apify Actor entry point."""
    async with Actor:
        # Get input
        actor_input = await Actor.get_input() or {}
        year = actor_input.get('year', 2026)

        Actor.log.info(f'Starting MZe SZIF scraper for year {year}')

        # Create registry
        registry = SubScraperRegistry()

        # Register MZe scraper
        mze_scraper = MZeSZIFCzScraper()
        registry.register(mze_scraper)

        Actor.log.info(f'Registered scrapers: {registry.list_scrapers()}')

        # Run autonomous scraping
        Actor.log.info('Starting autonomous scrape...')
        all_grants = await mze_scraper.scrape_all_programs(year=year)

        Actor.log.info(f'Scraping complete: {len(all_grants)} grants extracted')

        # Convert to dict and push to dataset
        for grant in all_grants:
            grant_dict = grant.to_dict()
            await Actor.push_data(grant_dict)

        # Statistics
        with_funding = sum(1 for g in all_grants if g.funding_amounts)
        with_deadline = sum(1 for g in all_grants if g.additional_metadata.get('deadline'))
        with_desc = sum(1 for g in all_grants if g.description and len(g.description) > 10)
        with_documents = sum(1 for g in all_grants if g.documents)

        # Set output metadata
        await Actor.set_value('OUTPUT', {
            'metadata': {
                'source': 'MZe SZIF',
                'scraper': 'MZeSZIFCzScraper',
                'year': year,
                'total_grants': len(all_grants),
            },
            'statistics': {
                'total': len(all_grants),
                'with_funding': with_funding,
                'with_deadline': with_deadline,
                'with_description': with_desc,
                'with_documents': with_documents,
            }
        })

        Actor.log.info('Statistics:')
        Actor.log.info(f'  Total grants: {len(all_grants)}')
        Actor.log.info(f'  With funding info: {with_funding}/{len(all_grants)} ({with_funding/len(all_grants)*100:.1f}%)')
        Actor.log.info(f'  With deadline: {with_deadline}/{len(all_grants)} ({with_deadline/len(all_grants)*100:.1f}%)')
        Actor.log.info(f'  With description: {with_desc}/{len(all_grants)} ({with_desc/len(all_grants)*100:.1f}%)')
        Actor.log.info(f'  With documents: {with_documents}/{len(all_grants)} ({with_documents/len(all_grants)*100:.1f}%)')

        Actor.log.info('✅ Actor finished successfully')


if __name__ == '__main__':
    asyncio.run(main())
