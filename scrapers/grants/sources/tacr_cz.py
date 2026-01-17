"""
Sub-scraper for tacr.cz (Technology Agency of the Czech Republic).
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


class TACRCzScraper(AbstractGrantSubScraper):
    """Scraper for tacr.cz grant calls"""

    DOMAIN = "tacr.cz"
    DOMAIN_ALT = "tacr.gov.cz"

    # Document type classification patterns
    DOC_TYPE_PATTERNS = {
        'call_text': ['zadávací dokumentace', 'zadavaci dokumentace', 'text výzvy'],
        'template': ['vzor', 'formulář', 'priloha', 'příloha'],
        'guidelines': ['příručka', 'metodika', 'pravidla'],
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def can_handle(self, url: str) -> bool:
        """Check if URL is from tacr.cz or tacr.gov.cz"""
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in [self.DOMAIN, self.DOMAIN_ALT])

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """Extract content from tacr.cz grant/program page"""
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else grant_metadata.get('title', '')

            # Extract description
            description_div = soup.select_one('.main__container') or soup.select_one('.entry-content')
            description = description_div.get_text(strip=True) if description_div else None

            # Extract summary
            summary = grant_metadata.get('summary', title)

            # Extract documents
            documents = self._extract_documents(soup, url)

            # Extract funding (often in text, hard to parse precisely without LLM)
            funding_amounts = None
            if description:
                # Look for patterns like "alokace ... mil. Kč"
                match = re.search(r'alokace\s*([\d\s,]+)\s*mil\.', description, re.IGNORECASE)
                if match:
                    try:
                        amount = float(match.group(1).replace(' ', '').replace(',', '.')) * 1_000_000
                        funding_amounts = {"total": int(amount), "currency": "CZK"}
                    except:
                        pass

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=summary,
                funding_amounts=funding_amounts,
                documents=documents,
                application_url=self._extract_application_url(soup),
                contact_email=self._extract_contact_email(description),
                eligible_recipients=None,
                additional_metadata={
                    'agency': 'TA ČR',
                },
                content_hash=generate_content_hash(title, url, description)
            )

            self.logger.info(f"Extracted content from {url} ({len(documents)} documents)")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract from {url}: {e}")
            return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract document links from files section"""
        documents = []
        # TA ČR uses .files__item or similar
        for item in soup.select('.files__item, .attachment-link, a[href*=".pdf"]'):
            try:
                if item.name == 'a':
                    link = item
                    doc_title = item.get_text(strip=True)
                else:
                    link = item.find('a', href=True) or item
                    title_elem = item.select_one('.files__title')
                    doc_title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

                if not link.has_attr('href'):
                    continue

                doc_url = urljoin(base_url, link['href'])
                if not any(ext in doc_url.lower() for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip']):
                    continue

                doc = Document(
                    title=doc_title,
                    url=doc_url,
                    doc_type=self._classify_document_type(doc_title),
                    file_format=doc_url.split('.')[-1].lower()[:4]
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
        link = soup.find('a', href=re.compile(r'ista\.tacr\.cz|sista\.tacr\.cz'))
        return link['href'] if link else None

    def _extract_contact_email(self, text: Optional[str]) -> Optional[str]:
        if not text: return None
        match = re.search(r'[\w\.-]+@tacr\.cz', text)
        return match.group(0) if match else None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        return download_document(doc_url, save_path)
