"""
Sub-scraper for opjak.cz (Operational Programme Jan Amos Komenský).
"""

import re
import logging
from typing import Optional, List
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import AbstractGrantSubScraper
from .models import GrantContent, Document
from .utils import download_document, generate_content_hash


class OPJAKCzScraper(AbstractGrantSubScraper):
    """Scraper for opjak.cz grant calls"""

    DOMAIN = "opjak.cz"

    # Document type classification patterns
    DOC_TYPE_PATTERNS = {
        'call_text': ['text výzvy', 'výzva', 'vyzva'],
        'template': ['vzor', 'příloha', 'priloha'],
        'guidelines': ['pravidla', 'metodika', 'příručka', 'prirucka'],
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def can_handle(self, url: str) -> bool:
        """Check if URL is from opjak.cz/vyzvy section"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc and "/vyzvy/" in url

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """Extract content from opjak.cz grant page"""
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else grant_metadata.get('title', '')

            # Extract description from "Základní informace" tab
            description_div = soup.find('div', id='zakladni-informace')
            description = description_div.get_text(strip=True) if description_div else None

            # Extract summary (perex)
            summary = description_div.find('p').get_text(strip=True) if description_div and description_div.find('p') else title

            # Extract funding amounts
            funding_amounts = self._extract_funding(soup)

            # Extract documents from "Dokumenty" tab
            documents = self._extract_documents(soup, url)

            # Extract contact email
            contact_email = None
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', description or '')
            if email_match:
                contact_email = email_match.group(0)

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=summary,
                funding_amounts=funding_amounts,
                documents=documents,
                application_url=self._extract_application_url(soup),
                contact_email=contact_email,
                eligible_recipients=self._extract_eligible_recipients(description),
                additional_metadata={
                    'programme': 'OP JAK',
                    'call_number': self._extract_call_number(title),
                },
                content_hash=generate_content_hash(title, url, description)
            )

            self.logger.info(f"Extracted content from {url} ({len(documents)} documents)")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract from {url}: {e}")
            return None

    def _extract_funding(self, soup: BeautifulSoup) -> Optional[dict]:
        """Extract allocation amount if visible"""
        allocation_elem = soup.find('p', class_='vyzva__top__label', string=re.compile('Celková alokace'))
        if allocation_elem:
            val_elem = allocation_elem.find_next_sibling('p', class_='vyzva__top__value')
            if val_elem:
                text = val_elem.get_text(strip=True)
                # e.g. "1 500 mil. Kč"
                match = re.search(r'([\d\s]+)\s*mil\.', text)
                if match:
                    amount = int(match.group(1).replace(' ', '')) * 1_000_000
                    return {"total": amount, "currency": "CZK"}
        return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract document links from the documents tab"""
        documents = []
        doc_tab = soup.find('div', id='dokumenty')
        if not doc_tab:
            return documents

        for doc_div in doc_tab.select('.doc'):
            try:
                link = doc_div.find('a', href=True)
                if not link:
                    continue

                doc_title = link.get_text(strip=True)
                doc_url = urljoin(base_url, link['href'])
                
                # Metadata from .doc__info p
                info_p = doc_div.select_one('.doc__info p')
                file_format = 'unknown'
                size = None
                if info_p:
                    info_text = info_p.get_text()
                    format_match = re.search(r'\|\s*([a-z]+)\s*\|', info_text, re.IGNORECASE)
                    if format_match:
                        file_format = format_match.group(1).lower()
                    
                    size_match = re.search(r'\|\s*([\d\.]+\s*[kMG]B)', info_text)
                    if size_match:
                        size = size_match.group(1)

                doc = Document(
                    title=doc_title,
                    url=doc_url,
                    doc_type=self._classify_document_type(doc_title),
                    file_format=file_format,
                    size=size
                )
                documents.append(doc)
            except Exception as e:
                self.logger.warning(f"Failed to extract document: {e}")
        
        return documents

    def _classify_document_type(self, title: str) -> str:
        title_lower = title.lower()
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(pattern in title_lower for pattern in patterns):
                return doc_type
        return 'other'

    def _extract_application_url(self, soup: BeautifulSoup) -> Optional[str]:
        link = soup.find('a', href=re.compile(r'iskp21\.mssf\.cz'))
        return link['href'] if link else None

    def _extract_call_number(self, title: str) -> Optional[str]:
        match = re.search(r'(\d{2}_\d{2}_\d{3})', title)
        return match.group(1) if match else None

    def _extract_eligible_recipients(self, description: Optional[str]) -> Optional[List[str]]:
        if not description:
            return None
        # Very basic extraction for now
        if "Oprávnění žadatelé" in description:
            # We would normally use a more sophisticated parser here
            pass
        return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        return download_document(doc_url, save_path)
