"""
Abstract base class for grant sub-scrapers.

Each operational program website (opst.cz, nrb.cz, etc.) has its own
scraper implementation that inherits from this base class.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Type, Any
import logging
import asyncio
import hashlib

from .models import GrantContent, Grant
from .registry import REGISTRY

class AbstractGrantSubScraper(ABC):
    """Base class for site-specific grant content extraction"""

    TOOL_NAME: str = "" # To be set by decorator/registry

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
    async def list_grants(self) -> List[Dict[str, Any]]:
        """
        Fetches the list of grant calls from the source's main listing page(s).

        Returns:
            A list of dictionaries, where each dict minimally contains:
            {'title': str, 'url': str, 'deadline': str (YYYY-MM-DD or None)}
        """
        pass
    
    @abstractmethod
    async def extract_content(self, url: str, grant_metadata: Dict[str, Any]) -> Optional[GrantContent]:
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
        # Fallback to class name if TOOL_NAME isn't set by decorator
        return getattr(self, 'TOOL_NAME', self.__class__.__name__)

    async def fetch_with_retries(self, tool: str, url: str, **kwargs) -> Any:
        """Placeholder for fetching utility, assumed to exist in actual scraping context."""
        self.logger.info(f"Fetching {url} using tool: {tool}")
        # In a real environment, this would be replaced by an HTTP client call
        # For now, we mock success, as we can't execute external HTTP calls in this context cleanly.
        await asyncio.sleep(0.1) 
        return "MOCK_HTML_CONTENT" 

    def create_grant_from_metadata(self, metadata: Dict[str, Any]) -> Grant:
        """Converts listing metadata (from list_grants) into a PRD-compliant Grant object."""
        # This mapping needs to be highly specific to the source implementation
        
        # Default mapping based on PRD minimums
        return Grant(
            title=metadata.get('title', 'No Title Found'),
            source=metadata.get('source', 'N/A'),
            sourceName=metadata.get('sourceName', self.get_scraper_name()),
            grantUrl=metadata.get('url'),
            deadline=metadata.get('deadline'),
            status="partial",
            statusNotes=f"Listing metadata collected by {self.get_scraper_name()}",
            contentHash=hashlib.sha256(str(metadata).encode()).hexdigest()
        )

