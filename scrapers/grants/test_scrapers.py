#!/usr/bin/env python3
"""
Quick test to verify scrapers work in Apify environment.
Tests MZ scraper (new) and GACR scraper (from grant-agencies).
"""

import asyncio
import logging
from apify import Actor

from sources.mz_gov_cz import MZGovCzScraper
from sources.gacr_cz import GACRCzScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    async with Actor:
        logger.info("=" * 80)
        logger.info("Testing scrapers in Apify environment")
        logger.info("=" * 80)
        
        # Test URLs
        mz_test_url = "https://mzd.gov.cz/dotacni-program-podpora-cinnosti-hospiců-2026"
        gacr_test_url = "https://gacr.cz/projekty-2025/"
        
        # Initialize scrapers
        mz_scraper = MZGovCzScraper(enable_llm=False)
        gacr_scraper = GACRCzScraper(enable_llm=False)
        
        logger.info("\n--- Test 1: MZ Scraper (nový) ---")
        logger.info(f"Testing URL: {mz_test_url}")
        logger.info(f"Can handle: {mz_scraper.can_handle(mz_test_url)}")
        logger.info(f"Source: {mz_scraper.get_source_name()}")
        
        # Try to extract content
        try:
            content = await mz_scraper.extract_content(mz_test_url, {})
            if content:
                logger.info(f"✓ MZ extraction OK - Description length: {len(content.description or '')}")
                logger.info(f"  Documents: {len(content.documents)}")
            else:
                logger.warning("✗ MZ extraction returned None")
        except Exception as e:
            logger.error(f"✗ MZ extraction failed: {e}")
        
        logger.info("\n--- Test 2: GACR Scraper (z grant-agencies) ---")
        logger.info(f"Testing URL: {gacr_test_url}")
        logger.info(f"Can handle: {gacr_scraper.can_handle(gacr_test_url)}")
        
        # Try to extract content
        try:
            content = await gacr_scraper.extract_content(gacr_test_url, {})
            if content:
                logger.info(f"✓ GACR extraction OK - Description length: {len(content.description or '')}")
                logger.info(f"  Documents: {len(content.documents)}")
            else:
                logger.warning("✗ GACR extraction returned None")
        except Exception as e:
            logger.error(f"✗ GACR extraction failed: {e}")
        
        logger.info("\n" + "=" * 80)
        logger.info("Test complete!")
        logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
