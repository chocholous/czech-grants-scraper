"""
Sub-scraper for esfcr.cz (OP Zaměstnanost Plus - Employment Programme).

Extracts grant calls from Liferay portal-based employment programme website.
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


class ESFCRCzScraper(AbstractGrantSubScraper):
    """Scraper for esfcr.cz OP Zaměstnanost Plus grant calls"""

    DOMAIN = "esfcr.cz"
    BASE_URL = "https://www.esfcr.cz"

    DOC_TYPE_PATTERNS = {
        'call_text': ['text výzvy'],
        'annex': ['příloha'],
        'template': ['vzor', 'šablona', 'prohlášení'],
        'guidelines': ['příručka', 'pokyny'],
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def can_handle(self, url: str) -> bool:
        """Check if URL is from esfcr.cz domain"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """Extract content from esfcr.cz grant page"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract metadata from Czech text patterns
            metadata = self._extract_metadata(soup)
            
            description = self._extract_description(soup)
            funding = self._extract_funding(soup, metadata)
            documents = self._extract_documents(soup, url)
            application_url = self._extract_application_url(soup)
            contact_email = self._extract_contact_email(soup)

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=grant_metadata.get('title'),
                funding_amounts=funding,
                documents=documents,
                application_url=application_url,
                contact_email=contact_email,
                eligible_recipients=None,
                additional_metadata=metadata,
            )

            self.logger.info(f"Extracted content from {url}: {len(documents)} documents")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract from {url}: {e}")
            return None

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """Extract metadata from Czech text patterns"""
        metadata = {}
        text = soup.get_text()
        
        # Extract call number: "Číslo: 071"
        call_match = re.search(r'Číslo[:\s]+(\d+)', text)
        if call_match:
            metadata['call_number'] = call_match.group(1)
        
        # Extract dates: "Platnost do: 5. 3. 2026 12:00"
        date_patterns = {
            'opens': r'Platnost od[:\s]+([\d\.\s:]+)',
            'closes': r'Platnost do[:\s]+([\d\.\s:]+)',
        }
        for key, pattern in date_patterns.items():
            match = re.search(pattern, text)
            if match:
                metadata[key] = match.group(1).strip()
        
        # Extract application count
        app_match = re.search(r'Aplikací[:\s]+(\d+)', text)
        if app_match:
            metadata['applications'] = int(app_match.group(1))
        
        return metadata

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract description from main content"""
        # Find all paragraphs, exclude navigation
        paragraphs = soup.find_all('p')
        if paragraphs:
            text_parts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                # Skip empty and navigation paragraphs
                if text and len(text) > 20:
                    text_parts.append(text)
            return '\n\n'.join(text_parts[:10])  # First 10 substantial paragraphs
        return None

    def _extract_funding(self, soup: BeautifulSoup, metadata: Dict) -> Optional[Dict]:
        """Extract funding amounts"""
        text = soup.get_text()
        
        # Pattern: "Alokace v Kč: 635 000 000"
        alloc_match = re.search(r'Alokace.*?(\d+(?:\s+\d{3})+)\s*[Kč]?', text)
        if alloc_match:
            amount_str = alloc_match.group(1).replace(' ', '')
            return {
                'total': int(amount_str),
                'currency': 'CZK',
            }
        return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract documents from Liferay document library"""
        documents = []
        
        # Find all document links (/documents/ paths)
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/documents/' in href:
                title = link.get_text(strip=True) or 'Document'
                
                # Convert relative to absolute
                doc_url = urljoin(base_url, href)
                
                # Determine format from URL
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

    def _extract_application_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract application portal URL"""
        text = soup.get_text()
        url_match = re.search(r'https?://iskp21\.mssv\.cz[^\s]*', text)
        if url_match:
            return url_match.group(0)
        return None

    def _extract_contact_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract contact email"""
        text = soup.get_text()
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            return email_match.group(0)
        return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """Download document"""
        return download_document(doc_url, save_path)
