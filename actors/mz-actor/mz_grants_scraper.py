"""
Wrapper for Apify CLI compatibility.
CLI tries to run: python -m mz-actor
This file makes it work.
"""

import asyncio
from src.main import main

if __name__ == '__main__':
    asyncio.run(main())
