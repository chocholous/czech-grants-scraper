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

    def can_handle(self, url: str) -> bool:
        """Check if URL is from sfzp domain"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(
        self, url: str, grant_metadata: dict, use_llm: Optional[bool] = None
    ) -> Optional[GrantContent]:
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

            # LLM enrichment (optional)
            for elem in soup.select("nav, footer, script, style, header"):
                elem.decompose()
            page_text = soup.get_text(" ", strip=True)
            content = await self.enrich_with_llm(content, page_text, use_llm)

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
        """Extract documents from page - handles multiple patterns"""
        documents = []
        seen_urls = set()

        # Pattern 1: Look for direct document links anywhere on the page
        # SFZP uses /files/documents/ pattern for downloads
        for link in soup.find_all('a', href=True):
            href = link['href']

            # Check for document file patterns
            is_document = (
                '/files/documents/' in href or
                any(ext in href.lower() for ext in ['.pdf', '.xlsx', '.docx', '.zip', '.xls', '.doc'])
            )

            if not is_document:
                continue

            doc_url = urljoin(base_url, href)

            # Skip duplicates
            if doc_url in seen_urls:
                continue
            seen_urls.add(doc_url)

            title = link.get_text(strip=True) or 'Document'
            # Skip generic download links like "stáhnout" - try to get title from parent
            if title.lower() in ['stáhnout', 'download', 'ke stažení']:
                parent = link.find_parent(['li', 'p', 'div'])
                if parent:
                    # Try to find a better title from parent text
                    parent_text = parent.get_text(strip=True)
                    # Remove the download text
                    for skip in ['stáhnout', 'download', 'ke stažení']:
                        parent_text = parent_text.replace(skip, '').strip()
                    if parent_text:
                        title = parent_text[:100]  # Limit length

            # Get file format from URL
            file_format = self._get_file_format(href)
            doc_type = self._classify_document(title)

            doc = Document(
                title=title,
                url=doc_url,
                doc_type=doc_type,
                file_format=file_format,
            )
            documents.append(doc)

        return documents

    def _get_file_format(self, url: str) -> str:
        """Extract file format from URL"""
        # Handle /files/documents/storage/... pattern
        url_lower = url.lower()
        for ext in ['pdf', 'xlsx', 'xls', 'docx', 'doc', 'zip']:
            if f'.{ext}' in url_lower:
                return ext
        return 'unknown'

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
