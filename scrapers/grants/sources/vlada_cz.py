"""
Sub-scraper for vlada.cz (Government Office / Úřad vlády).
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


class VladaCzScraper(AbstractGrantSubScraper):
    """Scraper for vlada.cz grant calls"""

    DOMAIN = "vlada.cz"

    # Document type classification patterns
    DOC_TYPE_PATTERNS = {
        'call_text': ['výzva', 'vyzva', 'text'],
        'guidelines': ['metodika', 'příručka', 'pokyny', 'pravidla'],
        'template': ['vzor', 'formulář', 'šablona'],
        'budget': ['rozpočet', 'kalkulačka', 'náklad'],
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def can_handle(self, url: str) -> bool:
        """Check if URL is from vlada.cz"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """Extract content from vlada.cz grant page"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else grant_metadata.get('title', '')

            # Extract description
            description = self._extract_description(soup)

            # Extract documents
            documents = self._extract_documents(soup, url)

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=title,
                funding_amounts=None,
                documents=documents,
                application_url=None,
                contact_email=self._extract_contact_email(soup),
                eligible_recipients=None,
                additional_metadata={
                    'programme': 'Úřad vlády ČR',
                }
            )

            # Generate content hash
            content.content_hash = generate_content_hash(title, url, description)

            self.logger.info(f"Extracted {len(documents)} documents from {url}")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract from {url}: {e}")
            return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract description from main content area"""
        # vlada.cz often uses .content-body or similar
        content_elem = soup.select_one('.content-body, .article, #main-content, main')
        if not content_elem:
            return None
        
        return content_elem.get_text("\n\n", strip=True)

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract document links from page"""
        documents = []
        
        for link in soup.select('a[href*=".pdf"], a[href*=".docx"], a[href*=".xlsx"], a[href*=".zip"]'):
            try:
                doc_title = link.get_text(strip=True) or link.get('title', 'Attachment')
                href = link['href']
                doc_url = urljoin(base_url, href)
                
                file_format = doc_url.split('.')[-1].lower()
                doc_type = self._classify_document_type(doc_title)
                
                doc = Document(
                    title=doc_title,
                    url=doc_url,
                    doc_type=doc_type,
                    file_format=file_format
                )
                documents.append(doc)
            except Exception:
                continue
                
        return documents

    def _classify_document_type(self, title: str) -> str:
        """Classify document based on title"""
        title_lower = title.lower()
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(pattern in title_lower for pattern in patterns):
                return doc_type
        return 'other'

    def _extract_contact_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract contact email"""
        email_link = soup.select_one('a[href^="mailto:"]')
        if email_link:
            return email_link.get('href').replace('mailto:', '').split('?')[0]
        return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        return download_document(doc_url, save_path)
