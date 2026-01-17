"""
Sub-scraper for eagri.cz and szif.cz (Ministry of Agriculture / MZe).

Extracts full grant content from Ministry of Agriculture and SZIF pages.
"""

import re
import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import AbstractGrantSubScraper
from .models import GrantContent, Document
from .utils import download_document, generate_content_hash


class MZeCzScraper(AbstractGrantSubScraper):
    """Scraper for eagri.cz and szif.cz grant calls"""

    # Domain identifiers for routing
    DOMAINS = ["eagri.cz", "szif.cz"]

    # Document type classification patterns
    DOC_TYPE_PATTERNS = {
        'call_text': ['text výzvy', 'znění výzvy', 'plné znění'],
        'guidelines': ['příručka', 'guidelines', 'pokyny', 'metodika'],
        'template': ['vzor', 'template', 'šablona', 'formulář'],
        'budget': ['rozpočet', 'budget', 'kalkulace', 'kalkulačka'],
        'faq': ['faq', 'časté dotazy', 'otázky a odpovědi'],
        'annex': ['příloha', 'annex', 'attachment'],
    }

    def can_handle(self, url: str) -> bool:
        """Check if URL is from MZe or SZIF domains"""
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in self.DOMAINS)

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """
        Extract full grant content from MZe or SZIF page.
        """
        try:
            # Fetch page HTML
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            parsed_url = urlparse(url)
            if "szif.cz" in parsed_url.netloc:
                return await self._extract_szif(url, soup, grant_metadata)
            else:
                return await self._extract_eagri(url, soup, grant_metadata)

        except Exception as e:
            self.logger.error(f"Failed to extract content from {url}: {e}")
            return None

    async def _extract_eagri(self, url: str, soup: BeautifulSoup, grant_metadata: dict) -> GrantContent:
        """Extract content from eagri.cz"""
        description = self._extract_description_eagri(soup)
        summary = self._extract_summary_eagri(soup)
        documents = self._extract_documents_eagri(soup, url)
        
        # MZe often has a table with basic info
        metadata = self._extract_metadata_eagri(soup)

        return GrantContent(
            source_url=url,
            scraper_name=self.get_scraper_name(),
            scraped_at=datetime.now(timezone.utc),
            description=description,
            summary=summary,
            documents=documents,
            additional_metadata=metadata,
            content_hash=generate_content_hash(grant_metadata.get('title', ''), url, description)
        )

    async def _extract_szif(self, url: str, soup: BeautifulSoup, grant_metadata: dict) -> GrantContent:
        """Extract content from szif.cz"""
        description = self._extract_description_szif(soup)
        summary = self._extract_summary_szif(soup)
        documents = self._extract_documents_szif(soup, url)
        metadata = self._extract_metadata_szif(soup)

        return GrantContent(
            source_url=url,
            scraper_name=self.get_scraper_name(),
            scraped_at=datetime.now(timezone.utc),
            description=description,
            summary=summary,
            documents=documents,
            additional_metadata=metadata,
            content_hash=generate_content_hash(grant_metadata.get('title', ''), url, description)
        )

    # ===== eagri.cz extraction methods =====

    def _extract_metadata_eagri(self, soup: BeautifulSoup) -> dict:
        metadata = {}
        # Eagri often uses tables or definition lists for metadata
        for row in soup.select('table tr'):
            cols = row.find_all(['td', 'th'])
            if len(cols) == 2:
                key = cols[0].get_text(strip=True).rstrip(':')
                value = cols[1].get_text(strip=True)
                metadata[key] = value
        return metadata

    def _extract_description_eagri(self, soup: BeautifulSoup) -> Optional[str]:
        # Main content is usually in .ea-content or .article-body
        content_elem = soup.select_one('.ea-content, .article-body, #content')
        if not content_elem:
            return None
        return content_elem.get_text(strip=True, separator='\n\n')

    def _extract_summary_eagri(self, soup: BeautifulSoup) -> Optional[str]:
        perex = soup.select_one('.ea-perex, .perex, .summary')
        if perex:
            return perex.get_text(strip=True)
        return None

    def _extract_documents_eagri(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        documents = []
        # Documents are often in .ea-attachment or similar
        for link in soup.select('a[href*="/public/portal/"]'):
            href = link.get('href')
            if not href or not any(ext in href.lower() for ext in ['.pdf', '.doc', '.xls', '.zip']):
                continue
            
            title = link.get_text(strip=True)
            if not title:
                title = Path(href).name
                
            doc_url = urljoin(base_url, href)
            file_format = self._get_file_format(doc_url)
            doc_type = self._classify_document_type(title)
            
            documents.append(Document(
                title=title,
                url=doc_url,
                doc_type=doc_type,
                file_format=file_format
            ))
        return documents

    # ===== szif.cz extraction methods =====

    def _extract_metadata_szif(self, soup: BeautifulSoup) -> dict:
        metadata = {}
        # SZIF has various layouts, often using specific classes
        for label in soup.select('.label'):
            value = label.find_next_sibling('.value')
            if value:
                metadata[label.get_text(strip=True)] = value.get_text(strip=True)
        return metadata

    def _extract_description_szif(self, soup: BeautifulSoup) -> Optional[str]:
        content_elem = soup.select_one('.content, .main-content, #main')
        if not content_elem:
            return None
        return content_elem.get_text(strip=True, separator='\n\n')

    def _extract_summary_szif(self, soup: BeautifulSoup) -> Optional[str]:
        perex = soup.select_one('.perex, .intro')
        if perex:
            return perex.get_text(strip=True)
        return None

    def _extract_documents_szif(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        documents = []
        for link in soup.select('a[href*="/cs/CmDocument"]'):
            href = link.get('href')
            if not href:
                continue
                
            title = link.get_text(strip=True) or link.get('title') or Path(href).name
            doc_url = urljoin(base_url, href)
            file_format = self._get_file_format(doc_url)
            doc_type = self._classify_document_type(title)
            
            documents.append(Document(
                title=title,
                url=doc_url,
                doc_type=doc_type,
                file_format=file_format
            ))
        return documents

    # ===== Common methods =====

    def _classify_document_type(self, title: str) -> str:
        title_lower = title.lower()
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in title_lower:
                    return doc_type
        return 'other'

    def _get_file_format(self, url: str) -> str:
        path = Path(urlparse(url).path)
        suffix = path.suffix.lower().lstrip('.')
        if not suffix and "CmDocument" in url:
            # SZIF uses CmDocument?rid=... and often lacks extension in URL
            return 'pdf' # Default for SZIF docs
        return suffix if suffix else 'pdf'

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        return download_document(doc_url, save_path)

    def get_scraper_name(self) -> str:
        return "MZeCzScraper"
