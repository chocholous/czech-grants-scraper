"""
Sub-scraper for mkcr.cz (Ministry of Culture of the Czech Republic).
"""

import re
import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import AbstractGrantSubScraper
from .models import GrantContent, Document
from .utils import download_document, generate_content_hash


class MKCRCzScraper(AbstractGrantSubScraper):
    """Scraper for mkcr.cz grant calls"""

    DOMAIN = "mkcr.cz"

    def can_handle(self, url: str) -> bool:
        """Check if URL is from mkcr.cz domain"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """Extract content from mkcr.cz grant page"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # MKCR often has content in .article or .content-inner
            content_elem = soup.select_one('.article') or soup.select_one('.content-inner') or soup.select_one('#main-content')
            
            description = self._extract_text(content_elem)
            documents = self._extract_documents(soup, url)

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=grant_metadata.get('title'),
                funding_amounts=self._extract_funding(description),
                documents=documents,
                additional_metadata=self._extract_metadata(soup),
            )
            
            # Generate content hash
            content.content_hash = generate_content_hash(
                title=grant_metadata.get('title', ''),
                url=url,
                description=description
            )

            return content
        except Exception as e:
            self.logger.error(f"Failed to extract from {url}: {e}")
            return None

    def _extract_text(self, elem: Optional[BeautifulSoup]) -> Optional[str]:
        if not elem:
            return None
        # Clean up
        for unwanted in elem.select('.social-share, footer, nav'):
            unwanted.decompose()
        return elem.get_text(strip=True, separator='\n\n')

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        documents = []
        for link in soup.select('a[href*=".pdf"], a[href*=".doc"], a[href*=".xls"], a[href*=".zip"]'):
            href = link.get('href')
            if href:
                title = link.get_text(strip=True) or "Document"
                doc_url = urljoin(base_url, href)
                ext = doc_url.split('.')[-1].lower()
                documents.append(Document(
                    title=title,
                    url=doc_url,
                    doc_type='other',
                    file_format=ext
                ))
        return documents

    def _extract_funding(self, text: Optional[str]) -> Optional[Dict]:
        if not text:
            return None
        match = re.search(r'([\d\s,]+)\s*(?:Kč|CZK)', text)
        if match:
            amount_str = match.group(1).replace('\xa0', '').replace(' ', '')
            try:
                amount = float(amount_str.replace(',', '.'))
                return {'total': amount, 'currency': 'CZK'}
            except ValueError:
                pass
        return None

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        metadata = {}
        date_elem = soup.select_one('.date, time')
        if date_elem:
            metadata['vydáno'] = date_elem.get_text(strip=True)
        return metadata

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        return download_document(doc_url, save_path)
