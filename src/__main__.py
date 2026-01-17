"""
Czech Grants Scraper - Apify Actor
Module entry point
"""

from .main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
