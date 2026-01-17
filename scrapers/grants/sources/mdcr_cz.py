"""
Sub-scraper for mdcr.cz and opd.cz (Ministry of Transport / MD).

Extracts full grant content from Ministry of Transport and OP Doprava pages.
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


class MDCrScraper(AbstractGrantSubScraper):
    """Scraper for mdcr.cz and opd.cz grant calls"""

    # Domain identifiers for routing
    DOMAINS = ["mdcr.cz", "opd.cz"]

    def can_handle(self, url: str) -> bool:
        """Check if URL is from MD or OPD domains"""
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in self.DOMAINS)

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """
        Extract full grant content from MD or OPD page.
        """
        try:
            # Fetch page HTML
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            parsed_url = urlparse(url)
            if "opd.cz" in parsed_url.netloc:
                return await self._extract_opd(url, soup, grant_metadata)
            else:
                return await self._extract_mdcr(url, soup, grant_metadata)

        except Exception as e:
            self.logger.error(f"Failed to extract content from {url}: {e}")
            return None

    async def _extract_mdcr(self, url: str, soup: BeautifulSoup, grant_metadata: dict) -> GrantContent:
        """Extract content from mdcr.cz"""
        # MDCR often has content in .article-content or #main
        content_elem = soup.select_one('.article-content, #main, .content')
        description = content_elem.get_text(strip=True, separator='\n\n') if content_elem else None
        
        # Summary is often the first paragraph
        summary = None
        if content_elem:
            first_p = content_elem.select_one('p')
            summary = first_p.get_text(strip=True) if first_p else None

        documents = []
        for link in soup.select('a[href*="/getmedia/"], a[href$=".pdf"], a[href$=".doc"], a[href$=".docx"]'):
            href = link.get('href')
            if not href:
                continue
            doc_url = urljoin(url, href)
            title = link.get_text(strip=True) or Path(doc_url).name
            documents.append(Document(
                title=title,
                url=doc_url,
                doc_type='other',
                file_format=self._get_file_format(doc_url)
            ))

        return GrantContent(
            source_url=url,
            scraper_name=self.get_scraper_name(),
            scraped_at=datetime.now(timezone.utc),
            description=description,
            summary=summary,
            documents=documents,
            content_hash=generate_content_hash(grant_metadata.get('title', ''), url, description)
        )

    async def _extract_opd(self, url: str, soup: BeautifulSoup, grant_metadata: dict) -> GrantContent:
        """Extract content from opd.cz"""
        # OPD has a specific structure for calls
        content_elem = soup.select_one('.call-detail, .content, #main')
        description = content_elem.get_text(strip=True, separator='\n\n') if content_elem else None
        
        metadata = {}
        for row in soup.select('.metadata-row, tr'):
            cols = row.find_all(['td', 'th'])
            if len(cols) == 2:
                key = cols[0].get_text(strip=True).rstrip(':')
                value = cols[1].get_text(strip=True)
                metadata[key] = value

        documents = []
        for link in soup.select('.documents-list a, .attachments a, a[href$=".pdf"]'):
            href = link.get('href')
            if not href:
                continue
            doc_url = urljoin(url, href)
            title = link.get_text(strip=True) or Path(doc_url).name
            documents.append(Document(
                title=title,
                url=doc_url,
                doc_type='other',
                file_format=self._get_file_format(doc_url)
            ))

        return GrantContent(
            source_url=url,
            scraper_name=self.get_scraper_name(),
            scraped_at=datetime.now(timezone.utc),
            description=description,
            documents=documents,
            additional_metadata=metadata,
            content_hash=generate_content_hash(grant_metadata.get('title', ''), url, description)
        )

    def _get_file_format(self, url: str) -> str:
        path = Path(urlparse(url).path)
        suffix = path.suffix.lower().lstrip('.')
        return suffix if suffix else 'pdf'

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        return download_document(doc_url, save_path)

    def get_scraper_name(self) -> str:
        return "MDCrScraper"
