"""
Sub-scraper for gacr.cz (Grant Agency of the Czech Republic).
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


class GACRCzScraper(AbstractGrantSubScraper):
    """Scraper for gacr.cz grant calls"""

    DOMAIN = "gacr.cz"

    # Document type classification patterns
    DOC_TYPE_PATTERNS = {
        'call_text': ['zadávací dokumentace', 'zadavaci dokumentace', 'text výzvy'],
        'template': ['vzor', 'formulář', 'příloha'],
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def can_handle(self, url: str) -> bool:
        """Check if URL is from gacr.cz"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """Extract content from gacr.cz page"""
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else grant_metadata.get('title', '')

            # Extract description
            description_div = soup.select_one('.article') or soup.select_one('.entry-content')
            description = description_div.get_text(strip=True) if description_div else None

            # Extract documents
            documents = self._extract_documents(soup, url)

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=grant_metadata.get('summary', title),
                funding_amounts=None, # Usually in PDF
                documents=documents,
                application_url=self._extract_application_url(soup),
                contact_email=self._extract_contact_email(description),
                eligible_recipients=None,
                additional_metadata={
                    'agency': 'GA ČR',
                },
                content_hash=generate_content_hash(title, url, description)
            )

            self.logger.info(f"Extracted content from {url} ({len(documents)} documents)")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract from {url}: {e}")
            return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract document links from gacr.cz page"""
        documents = []
        for link in soup.select('.gacrAttachmentsStripe a, .attachment-link, a[href*="download-attachment"]'):
            try:
                doc_title = link.get('title') or link.get_text(strip=True)
                doc_url = urljoin(base_url, link['href'])
                
                # Check for file format in class or URL
                file_format = 'pdf' # Default for GA ČR
                if 'pdf' in doc_url.lower(): file_format = 'pdf'
                elif 'docx' in doc_url.lower(): file_format = 'docx'

                doc = Document(
                    title=doc_title,
                    url=doc_url,
                    doc_type=self._classify_document_type(doc_title),
                    file_format=file_format
                )
                documents.append(doc)
            except Exception:
                continue
        
        return documents

    def _classify_document_type(self, title: str) -> str:
        title_lower = title.lower()
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(pattern in title_lower for pattern in patterns):
                return doc_type
        return 'other'

    def _extract_application_url(self, soup: BeautifulSoup) -> Optional[str]:
        link = soup.find('a', href=re.compile(r'gris\.cz'))
        return link['href'] if link else None

    def _extract_contact_email(self, text: Optional[str]) -> Optional[str]:
        if not text: return None
        match = re.search(r'[\w\.-]+@gacr\.cz', text)
        return match.group(0) if match else None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        return download_document(doc_url, save_path)
