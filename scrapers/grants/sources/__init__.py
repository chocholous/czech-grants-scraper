"""
Sub-scrapers for extracting full grant content from external sources.

Each operational program has its own scraper that extracts:
- Full grant descriptions
- Document URLs (PDFs, XLSX, DOCX)
- Funding amounts
- Application portals
- Contact information
"""

from .models import GrantContent, Document
from .registry import SubScraperRegistry
from .base import AbstractGrantSubScraper

__all__ = [
    'GrantContent',
    'Document',
    'SubScraperRegistry',
    'AbstractGrantSubScraper',
]
