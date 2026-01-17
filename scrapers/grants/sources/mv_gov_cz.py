"""
Sub-scraper for mv.gov.cz (Ministry of Interior OP NSHV grants).

Extracts document lists from ASP.NET pages. Primary value is document
collection, not web page content.
"""

import re
import logging
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import AbstractGrantSubScraper
from .models import GrantContent, Document
from .utils import download_document


class MVGovCzScraper(AbstractGrantSubScraper):
    """Scraper for mv.gov.cz OP NSHV grant calls"""

    DOMAIN = "mv.gov.cz"
    PROGRAMME_IDENTIFIER = "fondyeu"

    # Document type classification patterns
    DOC_TYPE_PATTERNS = {
        'call_text': ['výzva', 'vyzva'],
        'template': ['vzor', 'podmínek', 'podminek'],
        'budget': ['kalkulačka', 'kalkulacka', 'náklad'],
        'revision': ['rev0', 'rev1', 'rev2', 'rev'],
    }

    def can_handle(self, url: str) -> bool:
        """Check if URL is from mv.gov.cz fondyeu section"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc and self.PROGRAMME_IDENTIFIER in url

    async def extract_content(
        self, url: str, grant_metadata: dict, use_llm: Optional[bool] = None
    ) -> Optional[GrantContent]:
        """
        Extract content from mv.gov.cz grant page.

        Note: Web pages have minimal content. Primary value is document extraction.
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else grant_metadata.get('title', '')

            # Extract call number (three-tier fallback)
            call_number = self._extract_call_number(title, soup, url)

            # Extract documents
            documents = self._extract_documents(soup, url)

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=None,  # Not available on web page
                summary=title,  # Use title as summary
                funding_amounts=None,  # Not on web page (in PDF)
                documents=documents,
                application_url=None,  # Not provided
                contact_email=None,  # Not on grant pages
                eligible_recipients=None,  # Not on web page
                additional_metadata={
                    'call_number_mv': call_number,
                    'programme': 'OP NSHV',
                    'grant_count': len(documents),
                }
            )

            self.logger.info(f"Extracted {len(documents)} documents from {url}")

            # LLM enrichment (optional)
            for elem in soup.select("nav, footer, script, style, header"):
                elem.decompose()
            page_text = soup.get_text(" ", strip=True)
            content = await self.enrich_with_llm(content, page_text, use_llm)

            return content

        except Exception as e:
            self.logger.error(f"Failed to extract from {url}: {e}")
            return None

    def _extract_call_number(self, title: str, soup: BeautifulSoup, url: str) -> str:
        """
        Extract call number with three-tier fallback strategy.

        1. Try title text (e.g., "17. výzva OP NSHV...")
        2. Try document filenames (e.g., "NSHV_Výzva_č._14_26_017.pdf")
        3. Return "unknown" and log warning
        """
        # Tier 1: Title pattern
        match = re.search(r'(\d+)\.\s*výzva', title, re.IGNORECASE)
        if match:
            return match.group(1)

        # Tier 2: Document filename pattern (look for _XX_YY_ZZZ pattern)
        doc_links = soup.select('a[href*="soubor/"]')
        for link in doc_links:
            filename = link.get('title', link.get_text())
            # Look for call number pattern like "14_26_017"
            match = re.search(r'(\d{2}_\d{2}_\d{3})', filename)
            if match:
                # Extract just the final number (e.g., "017" from "14_26_017")
                parts = match.group(1).split('_')
                if len(parts) == 3:
                    return parts[2].lstrip('0') or parts[2]  # "017" → "17"

        # Tier 3: Fallback
        self.logger.warning(f"Could not extract call number from {url}")
        return "unknown"

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract document links from page"""
        documents = []

        for link in soup.select('a[href*="soubor/"]'):
            try:
                # Get full document name from title attribute
                doc_title = link.get('title', link.get_text(strip=True))

                # Build full URL
                href = link['href']
                doc_url = urljoin(base_url, href) if not href.startswith('http') else href

                # Get file format from URL (ASP.NET pattern: /soubor/{filename}.{ext}.aspx)
                file_format = self._get_file_format(doc_url)

                # Parse metadata from parent <li> text
                li_elem = link.find_parent('li')
                size = None
                if li_elem:
                    li_text = li_elem.get_text()
                    size_match = re.search(r'(\d+(?:\.\d+)?)\s*kB', li_text)
                    if size_match:
                        size = size_match.group(1) + ' kB'

                # Classify document type
                doc_type = self._classify_document_type(doc_title)

                doc = Document(
                    title=doc_title,
                    url=doc_url,
                    doc_type=doc_type,
                    file_format=file_format,
                    size=size,
                    validity_date=None
                )

                documents.append(doc)

            except Exception as e:
                self.logger.warning(f"Failed to extract document: {e}")
                continue

        return documents

    def _classify_document_type(self, title: str) -> str:
        """Classify document based on title"""
        title_lower = title.lower()

        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(pattern in title_lower for pattern in patterns):
                return doc_type

        return 'other'

    def _get_file_format(self, url: str) -> str:
        """
        Extract file format from ASP.NET URL.

        Pattern: /soubor/{filename}.{ext}.aspx
        Example: /soubor/NSHV_Výzva.pdf.aspx → 'pdf'
        """
        match = re.search(r'\.([a-z]+)\.aspx$', url, re.IGNORECASE)
        if match:
            return match.group(1).lower()

        # Fallback to standard extension
        path = Path(urlparse(url).path)
        return path.suffix.lstrip('.').lower() or 'unknown'

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """Download document from mv.gov.cz ASP.NET handler"""
        return download_document(doc_url, save_path)
