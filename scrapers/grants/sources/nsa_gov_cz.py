"""
Sub-scraper for nsa.gov.cz (National Sports Agency / NSA).

Extracts full grant content from National Sports Agency grant pages.
"""

import re
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import AbstractGrantSubScraper
from .models import GrantContent, Document
from .utils import download_document, generate_content_hash


class NSAGovCzScraper(AbstractGrantSubScraper):
    """Scraper for nsa.gov.cz grant calls"""

    # Domain identifier for routing
    DOMAIN = "nsa.gov.cz"

    def can_handle(self, url: str) -> bool:
        """Check if URL is from nsa.gov.cz domain"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """
        Extract full grant content from nsa.gov.cz page.
        """
        try:
            # Fetch page HTML
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            description = self._extract_description(soup)
            summary = self._extract_summary(soup)
            documents = self._extract_documents(soup, url)
            metadata = self._extract_metadata(soup)
            
            # NSA often has funding amounts in the text
            funding_amounts = self._extract_funding_amounts(soup)

            return GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=summary,
                funding_amounts=funding_amounts,
                documents=documents,
                additional_metadata=metadata,
                content_hash=generate_content_hash(grant_metadata.get('title', ''), url, description)
            )

        except Exception as e:
            self.logger.error(f"Failed to extract content from {url}: {e}")
            return None

    def _extract_metadata(self, soup: BeautifulSoup) -> dict:
        metadata = {}
        # NSA uses various table structures
        for row in soup.select('table tr'):
            cols = row.find_all(['td', 'th'])
            if len(cols) == 2:
                key = cols[0].get_text(strip=True).rstrip(':')
                value = cols[1].get_text(strip=True)
                metadata[key] = value
        return metadata

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        # Main content is in .entry-content or article
        content_elem = soup.select_one('.entry-content, article, .content')
        if not content_elem:
            return None
        return content_elem.get_text(strip=True, separator='\n\n')

    def _extract_summary(self, soup: BeautifulSoup) -> Optional[str]:
        perex = soup.select_one('.perex, .intro')
        if perex:
            return perex.get_text(strip=True)
        return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        documents = []
        # Documents are usually links to PDFs
        for link in soup.select('a[href$=".pdf"], a[href$=".docx"], a[href*="/download/"]'):
            href = link.get('href')
            if not href:
                continue
            doc_url = urljoin(base_url, href)
            title = link.get_text(strip=True) or Path(doc_url).name
            documents.append(Document(
                title=title,
                url=doc_url,
                doc_type='other',
                file_format=self._get_file_format(doc_url)
            ))
        return documents

    def _extract_funding_amounts(self, soup: BeautifulSoup) -> Optional[dict]:
        text = soup.get_text()
        # Search for allocation patterns
        alloc_match = re.search(r'alokace[:\s]+([\d\s]+)\s*Kč', text, re.IGNORECASE)
        if alloc_match:
            amount_str = alloc_match.group(1).replace(' ', '')
            try:
                return {
                    'total': float(amount_str),
                    'currency': 'CZK'
                }
            except ValueError:
                pass
        return None

    def _get_file_format(self, url: str) -> str:
        path = Path(urlparse(url).path)
        suffix = path.suffix.lower().lstrip('.')
        return suffix if suffix else 'pdf'

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        return download_document(doc_url, save_path)

    def get_scraper_name(self) -> str:
        return "NSAGovCzScraper"
