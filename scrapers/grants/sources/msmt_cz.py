"""
Sub-scraper for msmt.cz (Ministry of Education, Youth and Sports).
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


class MSMTCzScraper(AbstractGrantSubScraper):
    """Scraper for msmt.cz grant calls (national grants)"""

    DOMAIN = "msmt.cz"
    DOMAIN_ALT = "msmt.gov.cz"

    # Document type classification patterns
    DOC_TYPE_PATTERNS = {
        'call_text': ['vyhlášení', 'text výzvy', 'výzva'],
        'template': ['vzor', 'formulář', 'příloha'],
        'result': ['výsledky', 'rozhodnutí'],
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def can_handle(self, url: str) -> bool:
        """Check if URL is from msmt.cz or msmt.gov.cz"""
        parsed = urlparse(url)
        # Avoid handling opjak.cz here even if it's mentioned on msmt.cz
        if "opjak.cz" in url:
            return False
        return any(domain in parsed.netloc for domain in [self.DOMAIN, self.DOMAIN_ALT])

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """Extract content from msmt.cz page"""
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title_elem = soup.find('h2') or soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else grant_metadata.get('title', '')

            # Extract description
            description_div = soup.select_one('.article-content') or soup.select_one('#content')
            description = description_div.get_text(strip=True) if description_div else None

            # Extract summary
            summary = grant_metadata.get('summary', title)

            # Extract documents
            documents = self._extract_documents(soup, url)

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=summary,
                funding_amounts=None,
                documents=documents,
                application_url=None,
                contact_email=self._extract_contact_email(description),
                eligible_recipients=None,
                additional_metadata={
                    'ministry': 'MŠMT',
                },
                content_hash=generate_content_hash(title, url, description)
            )

            self.logger.info(f"Extracted content from {url} ({len(documents)} documents)")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract from {url}: {e}")
            return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract document links from msmt.cz page"""
        documents = []
        content_div = soup.select_one('.article-content') or soup.select_one('#content')
        if not content_div:
            return documents

        for link in content_div.find_all('a', href=True):
            try:
                href = link['href']
                # msmt.cz often has links to /file/12345/ or similar
                if not ('.pdf' in href.lower() or '.doc' in href.lower() or '.xls' in href.lower() or '/file/' in href.lower()):
                    continue

                doc_title = link.get_text(strip=True) or link.get('title', 'Dokument')
                doc_url = urljoin(base_url, href)

                doc = Document(
                    title=doc_title,
                    url=doc_url,
                    doc_type=self._classify_document_type(doc_title),
                    file_format=self._guess_format(doc_url)
                )
                documents.append(doc)
            except Exception:
                continue
        
        return documents

    def _guess_format(self, url: str) -> str:
        url_lower = url.lower()
        if '.pdf' in url_lower: return 'pdf'
        if '.doc' in url_lower: return 'docx'
        if '.xls' in url_lower: return 'xlsx'
        return 'unknown'

    def _classify_document_type(self, title: str) -> str:
        title_lower = title.lower()
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(pattern in title_lower for pattern in patterns):
                return doc_type
        return 'other'

    def _extract_contact_email(self, text: Optional[str]) -> Optional[str]:
        if not text: return None
        match = re.search(r'[\w\.-]+@msmt\.cz', text)
        return match.group(0) if match else None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        return download_document(doc_url, save_path)
