"""
Sub-scraper for irop.mmr.cz (Integrovaný regionální operační program - IROP).

Extracts grant calls from Kentico CMS-based regional programme website.
Note: Domain redirects from irop.mmr.cz to irop.gov.cz
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
from .utils import download_document


class IROPGovCzScraper(AbstractGrantSubScraper):
    """Scraper for irop.gov.cz IROP grant calls"""

    DOMAINS = ["irop.mmr.cz", "irop.gov.cz"]
    BASE_URL = "https://irop.gov.cz"

    DOC_TYPE_PATTERNS = {
        'call_text': ['text výzvy', 'výzva'],
        'guidelines': ['pravidla', 'příručka', 'pokyny'],
        'template': ['vzor', 'šablona'],
        'annex': ['příloha'],
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def can_handle(self, url: str) -> bool:
        """Check if URL is from irop domain"""
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in self.DOMAINS)

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """Extract content from irop.gov.cz grant page"""
        try:
            # Follow redirects
            response = requests.get(url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.content, 'html.parser')

            description = self._extract_description(soup)
            funding = self._extract_funding(soup)
            documents = self._extract_documents(soup, response.url)
            metadata = self._extract_metadata(soup)

            content = GrantContent(
                source_url=response.url,  # Use final URL after redirects
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=grant_metadata.get('title'),
                funding_amounts=funding,
                documents=documents,
                application_url=None,
                contact_email=None,
                eligible_recipients=None,
                additional_metadata=metadata,
            )

            self.logger.info(f"Extracted content from {response.url}: {len(documents)} documents")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract from {url}: {e}")
            return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract description from main content"""
        # Look for main content containers
        for selector in ['.main-content', '.content', 'main', 'article']:
            content_div = soup.select_one(selector)
            if content_div:
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    return '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        return None

    def _extract_funding(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract funding amounts"""
        text = soup.get_text()
        
        # Pattern: "2 000 000 000 Kč" or "2 mld. Kč"
        patterns = [
            (r'(\d+)\s*mld\.?\s*[Kč€]', 1000000000),
            (r'(\d+)\s*mil\.?\s*[Kč€]', 1000000),
            (r'(\d+(?:\s+\d{3})+)\s*[Kč€]', 1),
        ]
        
        for pattern, multiplier in patterns:
            match = re.search(pattern, text)
            if match:
                num_str = match.group(1).replace(' ', '')
                amount = int(num_str) * multiplier
                # Determine currency
                currency = 'EUR' if '€' in match.group(0) else 'CZK'
                return {
                    'total': amount,
                    'currency': currency,
                }
        return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract documents from Kentico document management"""
        documents = []
        
        # Find all links to documents
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Look for document patterns
            if any(pattern in href.lower() for pattern in ['/getresource.ashx', '/getattachment', '.pdf', '.docx', '.xlsx']):
                title = link.get_text(strip=True)
                if not title or len(title) < 3:
                    # Try to get title from parent or aria-label
                    title = link.get('aria-label') or link.get('title') or 'Document'
                
                doc_url = urljoin(base_url, href)
                
                # Determine format
                file_format = 'unknown'
                for ext in ['pdf', 'docx', 'xlsx', 'zip']:
                    if f'.{ext}' in href.lower():
                        file_format = ext
                        break
                
                doc_type = self._classify_document(title)
                
                doc = Document(
                    title=title,
                    url=doc_url,
                    doc_type=doc_type,
                    file_format=file_format,
                )
                documents.append(doc)
        
        return documents

    def _classify_document(self, title: str) -> str:
        """Classify document by title"""
        title_lower = title.lower()
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(pattern in title_lower for pattern in patterns):
                return doc_type
        return 'other'

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """Extract metadata from page"""
        metadata = {}
        
        # Try to extract call number from title or URL
        title = soup.find('h1')
        if title:
            title_text = title.get_text()
            metadata['title'] = title_text
            
            # Extract call number: "118. výzva IROP"
            call_match = re.search(r'(\d+)\.\s*výzva', title_text, re.IGNORECASE)
            if call_match:
                metadata['call_number'] = call_match.group(1)
        
        return metadata

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """Download document"""
        return download_document(doc_url, save_path)
