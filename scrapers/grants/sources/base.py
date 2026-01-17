"""
Abstract base class for grant sub-scrapers.

Each operational program website (opst.cz, nrb.cz, etc.) has its own
scraper implementation that inherits from this base class.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging
from .models import GrantContent


class AbstractGrantSubScraper(ABC):
    """Base class for site-specific grant content extraction"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """
        Check if this scraper can handle the given URL.

        Args:
            url: Full URL to check (e.g., "https://opst.cz/dotace/101-vyzva/")

        Returns:
            True if this scraper handles this domain/pattern
        """
        pass

    @abstractmethod
    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """
        Extract full grant content from source page.

        Args:
            url: Full URL to the grant detail page
            grant_metadata: Metadata from dotaceeu.cz (title, call_number, etc.)

        Returns:
            GrantContent object with description, documents, funding amounts, etc.
            Returns None if extraction fails
        """
        pass

    @abstractmethod
    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """
        Download document to local filesystem.

        Args:
            doc_url: Full URL to document
            save_path: Absolute path where file should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        pass

    def get_scraper_name(self) -> str:
        """Return human-readable scraper name (e.g., 'OPSTCzScraper')"""
        return self.__class__.__name__
