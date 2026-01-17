"""
Sub-scraper for eeagrants.cz (EEA and Norway Grants in the Czech Republic).
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


class EEAGrantsCzScraper(AbstractGrantSubScraper):
    """Scraper for eeagrants.cz grant calls"""

    DOMAIN = "eeagrants.cz"

    def can_handle(self, url: str) -> bool:
        """Check if URL is from eeagrants.cz domain"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """Extract content from eeagrants.cz grant page"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            description = self._extract_description(soup)
            documents = self._extract_documents(soup, url)
            
            # Metadata from detail page
            metadata = self._extract_metadata(soup)

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=grant_metadata.get('title'),
                funding_amounts=self._extract_funding(soup),
                documents=documents,
                eligible_recipients=self._extract_recipients(soup),
                additional_metadata=metadata,
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

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        content = soup.select_one('.detailContent') or soup.select_one('article')
        if content:
            # Remove footer and social links
            for unwanted in content.select('footer, .PE_socialShare'):
                unwanted.decompose()
            return content.get_text(strip=True, separator='\n\n')
        return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        documents = []
        for link in soup.select('a[href*=".pdf"], a[href*=".doc"], a[href*=".xls"]'):
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

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        metadata = {}
        # Try to find date and author
        publish_date = soup.select_one('.publishDate')
        if publish_date:
            metadata['vydáno'] = publish_date.get_text(strip=True)
        
        author = soup.select_one('.author figcaption')
        if author:
            metadata['autor'] = author.get_text(strip=True)
            
        return metadata

    def _extract_funding(self, soup: BeautifulSoup) -> Optional[Dict]:
        text = soup.get_text()
        # Look for "alokace" or amounts in CZK/EUR
        match = re.search(r'alokace\s*[:\-]?\s*([\d\s,]+)\s*(Kč|EUR)', text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace('\xa0', '').replace(' ', '')
            try:
                amount = float(amount_str.replace(',', '.'))
                return {
                    'total': amount,
                    'currency': match.group(2).upper()
                }
            except ValueError:
                pass
        return None

    def _extract_recipients(self, soup: BeautifulSoup) -> Optional[List[str]]:
        text = soup.get_text()
        if 'Oprávnění žadatelé' in text:
            # This is hard to extract generically without better structure
            pass
        return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        return download_document(doc_url, save_path)
