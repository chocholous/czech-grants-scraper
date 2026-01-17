"""
Czech Grants Scraper - Apify Actor
Root entry point for Apify CLI compatibility
"""

import asyncio
from src.main import main

if __name__ == "__main__":
    asyncio.run(main())
