"""
Sub-scraper for sfzp.cz (State Environmental Fund - Modernizační fond).

Extracts grant calls from WordPress-based modernization fund website.
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


class SFZPCzScraper(AbstractGrantSubScraper):
    """Scraper for sfzp.cz Modernizační fond grant calls"""

    DOMAIN = "sfzp"  # Matches both sfzp.cz and sfzp.gov.cz
    BASE_URL = "https://sfzp.gov.cz"

    DOC_TYPE_PATTERNS = {
        'call_text': ['text výzvy', 'znění'],
        'guidelines': ['pokyny', 'příručka'],
        'template': ['vzor', 'šablona', 'prohlášení', 'protokol'],
        'budget': ['nástroj', 'výpočet', 'kalkulace'],
        'branding': ['grafický manuál'],
        'annex': ['příloha'],
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def can_handle(self, url: str) -> bool:
        """Check if URL is from sfzp domain"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """Extract content from sfzp.cz grant page"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract sections
            description = self._extract_description(soup)
            funding = self._extract_funding(soup)
            documents = self._extract_documents(soup, url)
            application_url = self._extract_application_url(soup)
            contact_email = self._extract_contact_email(soup)
            eligible_recipients = self._extract_eligible_recipients(soup)

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
                eligible_recipients=eligible_recipients,
                additional_metadata={},
            )

            self.logger.info(f"Extracted content from {url}: {len(documents)} documents")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract from {url}: {e}")
            return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract description from entry-content"""
        entry = soup.select_one('.entry-content')
        if entry:
            paragraphs = entry.find_all('p')
            return '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        return None

    def _extract_funding(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract funding with Czech billion/million parsing"""
        text = soup.get_text()
        
        # Pattern: "3 000 000 000 Kč" or "3 mld. Kč" or "50 mil. Kč"
        patterns = [
            (r'(\d+)\s*mld\.?\s*Kč', 1000000000),
            (r'(\d+)\s*mil\.?\s*Kč', 1000000),
            (r'(\d+(?:\s+\d{3})+)\s*Kč', 1),
        ]
        
        for pattern, multiplier in patterns:
            match = re.search(pattern, text)
            if match:
                num_str = match.group(1).replace(' ', '')
                amount = int(num_str) * multiplier
                return {
                    'total': amount,
                    'currency': 'CZK',
                }
        return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract documents from dual-link pattern"""
        documents = []
        
        # Find "Dokumenty ke stažení" section
        for h2 in soup.find_all('h2'):
            if 'dokumenty' in h2.get_text().lower():
                # Find all download links in following siblings
                sibling = h2.find_next_sibling()
                while sibling and sibling.name != 'h2':
                    # Look for direct download links
                    for link in sibling.find_all('a', href=True):
                        href = link['href']
                        if '/files/documents/' in href or any(ext in href.lower() for ext in ['.pdf', '.xlsx', '.docx', '.zip']):
                            title = link.get_text(strip=True) or 'Document'
                            # Skip "stáhnout" links, use title
                            if title.lower() != 'stáhnout':
                                doc_url = urljoin(self.BASE_URL, href)
                                file_format = href.split('.')[-1].lower()
                                doc_type = self._classify_document(title)
                                
                                doc = Document(
                                    title=title,
                                    url=doc_url,
                                    doc_type=doc_type,
                                    file_format=file_format,
                                )
                                documents.append(doc)
                    sibling = sibling.find_next_sibling()
                break
        
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
        url_match = re.search(r'https?://zadosti\.sfzp\.[^\s]*', text)
        if url_match:
            return url_match.group(0)
        return None

    def _extract_contact_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract contact email"""
        text = soup.get_text()
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@sfzp\.[A-Za-z]{2,}\b', text)
        if email_match:
            return email_match.group(0)
        return None

    def _extract_eligible_recipients(self, soup: BeautifulSoup) -> Optional[List[str]]:
        """Extract eligible recipients from 'Kdo může žádat' section"""
        for elem in soup.find_all(['h2', 'h3']):
            if 'kdo může' in elem.get_text().lower():
                next_list = elem.find_next(['ul', 'ol'])
                if next_list:
                    return [li.get_text(strip=True) for li in next_list.find_all('li')]
        return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """Download document"""
        return download_document(doc_url, save_path)
