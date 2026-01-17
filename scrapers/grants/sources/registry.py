"""
Sub-scraper registry for routing URLs to appropriate scrapers.

The registry maintains a list of available scrapers and routes
incoming URLs to the scraper that can handle them.
"""

from typing import Optional, List, Callable
import logging
from .base import AbstractGrantSubScraper

# Global registry instance to be imported and used by scrapers
REGISTRY = None

def register_scraper(scraper_name: str):
    """
    Decorator to register a Scraper class instance to the global registry.
    This assumes the registry is instantiated and available globally when imported.
    """
    def decorator(cls: type[AbstractGrantSubScraper]):
        global REGISTRY
        if REGISTRY is None:
            # This should ideally not happen if this file is imported correctly
            logging.error("REGISTRY is not initialized when trying to register a scraper.")
            return cls

        # Instantiate the class and register it
        instance = cls()
        # Overwrite the scraper name if provided via decorator for consistency
        setattr(instance, 'TOOL_NAME', scraper_name) 
        REGISTRY.register(instance)
        return cls
    return decorator

class SubScraperRegistry:
    """Registry for managing and routing to sub-scrapers"""

    def __init__(self):
        self._scrapers: List[AbstractGrantSubScraper] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def register(self, scraper: AbstractGrantSubScraper):
        """
        Register a new sub-scraper.

        Args:
            scraper: Instance of AbstractGrantSubScraper implementation
        """
        if not isinstance(scraper, AbstractGrantSubScraper):
            raise TypeError(f"Scraper must inherit from AbstractGrantSubScraper, got {type(scraper)}")

        self._scrapers.append(scraper)
        self.logger.info(f"Registered scraper: {scraper.get_scraper_name()}")

    def get_scraper_for_url(self, url: str) -> Optional[AbstractGrantSubScraper]:
        """
        Find the appropriate scraper for a given URL.

        Args:
            url: Full URL to check (e.g., "https://opst.cz/dotace/101-vyzva/")

        Returns:
            Scraper instance that can handle the URL, or None if no match found
        """
        for scraper in self._scrapers:
            if scraper.can_handle(url):
                self.logger.debug(f"Found scraper {scraper.get_scraper_name()} for URL: {url}")
                return scraper

        self.logger.warning(f"No scraper found for URL: {url}")
        return None

    def list_scrapers(self) -> List[str]:
        """
        Get list of all registered scraper names.

        Returns:
            List of scraper class names
        """
        return [scraper.get_scraper_name() for scraper in self._scrapers]

    def count(self) -> int:
        """Return number of registered scrapers"""
        return len(self._scrapers)

# Initialize the global registry instance upon module load
REGISTRY = SubScraperRegistry()
