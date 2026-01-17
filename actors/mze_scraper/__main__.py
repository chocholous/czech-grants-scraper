"""Entry point for Apify Actor."""

from src.main import main
import asyncio

if __name__ == '__main__':
    asyncio.run(main())
