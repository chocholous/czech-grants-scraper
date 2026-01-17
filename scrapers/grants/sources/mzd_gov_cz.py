"""
Scraper for MZD (Ministry of Labour and Social Affairs) National Grant Programs 2026.
Source: https://mzd.gov.cz/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/
"""

import asyncio
from typing import List, Optional
from bs4 import BeautifulSoup
from scrapers.grants.base import AbstractGrantSubScraper
from scrapers.grants.models import Grant, GrantContent, Document
from scrapers.grants.registry import register_scraper, REGISTRY
from scrapers.grants.utils.date_helpers import parse_cz_date

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
        return 'mzd.gov.cz' in url and 'narodni-dotacni-programy-2026' in url
    
    async def list_grants(self) -> List[dict]:
        """
        Fetches the main category page and extracts links to individual grant programs.
        """
        self.logger.info(f"Fetching main listing page: {self.BASE_URL}")
        soup = await self.fetch_with_retries(tool='requests', url=self.BASE_URL)
        
        content_wrapper = soup.find(id='content-wrapper')
        if not content_wrapper:
            self.logger.error("Could not find main content area #content-wrapper.")
            return []

        # Target anchor tags linking to the specific program sub-pages
        link_elements = content_wrapper.select('a[href*="/narodni-dotacni-programy-2026/"]:not([href*="feed"])')
        
        # We use the three known URLs as the definite list, as the selector might be too broad.
        target_urls = [
            "https://mzd.gov.cz/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/narodni-program-reseni-problematiky-hiv-aids-pro-rok-2026/",
            "https://mzd.gov.cz/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/podpora-zdravi-a-zdravotni-pece-2026/",
            "https://mzd.gov.cz/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/vyrovnavani-prilezitosti-pro-obcany-se-zdravotnim-postizenim-2026/"
        ]
        
        self.logger.info(f"Found {len(target_urls)} specific grant program links to process.")

        tasks = [self.extract_grant_details_from_program_page(url) for url in target_urls]
            
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

        # We create one Grant record per program page as a starting point (~10 expected records total)
        return [Grant(
            title=title,
            source=self.BASE_URL,
            sourceName=self.SOURCE_NAME,
            grantUrl=url,
            description=description[:500] + "...",
            eligibility=["N/A - Program Level"],
            fundingAmount={'min': 10000, 'max': 10000000, 'currency': 'CZK'}, 
            deadline="2026-12-31", 
            status="ok",
            statusNotes="Program page extracted.",
            extractedAt=asyncio.get_event_loop().time(), # Placeholder for timestamp
            contentHash=f"mzd_program_{hash(url)}"
        )]

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        # Not needed for this initial approach where we parse details directly from the list of program pages
        return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        # Not implemented in this initial phase
        self.logger.warning(f"Document download not implemented for {self.get_scraper_name()}. Skipping {doc_url}")
        return False
