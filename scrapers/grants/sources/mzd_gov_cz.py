"""
Scraper for MZD (Ministry of Labour and Social Affairs) National Grant Programs 2026.
Source: https://mzd.gov.cz/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/
"""

import asyncio
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin # <-- ADDED
from datetime import datetime, timezone # <-- ADDED
from bs4 import BeautifulSoup

from scrapers.grants.base import AbstractGrantSubScraper
from scrapers.grants.models import Grant, GrantContent, Document # <-- UPDATED IMPORT
from scrapers.grants.registry import register_scraper, REGISTRY
# Removed date_helpers import as it might not exist, relying on datetime from standard lib

# Using a common approach from other scrapers for self-registration
@register_scraper("mzd_gov_cz_2026")
class MzdGovCz2026Scraper(AbstractGrantSubScraper):
    """Scraper for MZD National Grant Programs 2026."""

    BASE_URL = "https://mzd.gov.cz/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/"
    SOURCE_NAME = "MZD Národní dotační programy 2026"
    
    def get_scraper_name(self) -> str:
        """Return human-readable scraper name (used by registry)."""
        return self.TOOL_NAME # TOOL_NAME is set by the decorator in registry.py

    def can_handle(self, url: str) -> bool:
        """Check if URL is from mzd.gov.cz and relevant path."""
        # This is primarily for the listing page, which triggers the scraping process.
        return 'mzd.gov.cz' in url and 'narodni-dotacni-programy-2026' in url
    
    async def list_grants(self) -> List[Dict[str, Any]]:
        """
        Fetches the main category page and extracts links to individual grant programs.
        """
        self.logger.info(f"Fetching main listing page: {self.BASE_URL}")
        # NOTE: We must use the base URL here, not the hardcoded program URLs,
        # for the registry/orchestrator to find this scraper first.
        soup = await self.fetch_with_retries(tool='requests', url=self.BASE_URL)
        
        content_wrapper = soup.find(id='content-wrapper')
        if not content_wrapper:
            self.logger.error("Could not find main content area #content-wrapper.")
            return []

        # Target anchor tags linking to the specific program sub-pages within the content area
        link_elements = content_wrapper.select('a[href*="/narodni-dotacni-programy-2026/"]:not([href*="feed"])')
        
        program_urls = []
        for element in link_elements:
            href = element.get('href')
            if href:
                full_url = urljoin(self.BASE_URL, href)
                if full_url not in program_urls:
                    program_urls.append(full_url)
        
        self.logger.info(f"Found {len(program_urls)} specific grant program links to process.")

        tasks = [self.extract_grant_details_from_program_page(url) for url in program_urls]
            
        all_grants = await asyncio.gather(*tasks)
        
        final_grants = []
        for grant_list in all_grants:
            final_grants.extend(grant_list)
            
        return final_grants


    async def extract_grant_details_from_program_page(self, url: str) -> List[Grant]:
        """
        Fetches an individual program page and extracts grant/program details.
        We treat each program page as a single, high-level grant record for now.
        """
        program_soup = await self.fetch_with_retries(tool='requests', url=url)
        
        # Extract Title from the primary H1/Title tag on the page
        title_element = program_soup.select_one('header h1')
        title = title_element.text.strip() if title_element else f"Grant Program at {url}"
        
        # Extract Description from the main content area
        content_wrapper = program_soup.select_one('#content-wrapper')
        description = content_wrapper.text.strip() if content_wrapper else "No detailed description found."
        
        self.logger.info(f"Extracted program: {title} from {url}")

        # Create a summary grant record based on the program page title/details
        metadata = {
            'title': title,
            'source': self.BASE_URL,
            'sourceName': self.SOURCE_NAME,
            'url': url,
            'deadline': "2026-12-31", # Placeholder, needs refinement
            'description': description[:500] + "...",
            'eligibility': ["N/A - Program Level"], # Placeholder
            'fundingAmount': {'min': 10000, 'max': 10000000, 'currency': 'CZK'}, # Placeholder
            'extractedAt': datetime.now(timezone.utc).isoformat(),
        }
        
        # Use the base class helper to map to the Grant type required by list_grants return
        return [self.create_grant_from_metadata(metadata)]

    async def extract_content(self, url: str, grant_metadata: Dict[str, Any]) -> Optional[GrantContent]:
        # Not required for this initial list-only extraction phase
        return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        # Not implemented in this initial phase
        self.logger.warning(f"Document download not implemented for {self.get_scraper_name()}. Skipping {doc_url}")
        return False
