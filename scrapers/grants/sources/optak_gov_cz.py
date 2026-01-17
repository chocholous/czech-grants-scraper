"""
Sub-scraper for optak.gov.cz (OP Technologie a aplikace pro konkurenceschopnost).

Extracts grant calls from custom Czech government website.
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


class OPTAKGovCzScraper(AbstractGrantSubScraper):
    """Scraper for optak.gov.cz OP TAK grant calls"""

    DOMAIN = "optak.gov.cz"
    BASE_URL = "https://optak.gov.cz"

    DOC_TYPE_PATTERNS = {
        'call_text': ['výzva', 'znění'],
        'guidelines': ['pravidla', 'př', 'příručka'],
        'template': ['vzor', 'šablona'],
        'annex': ['příloha'],
    }

    def can_handle(self, url: str) -> bool:
        """Check if URL is from optak.gov.cz domain"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(
        self, url: str, grant_metadata: dict, use_llm: Optional[bool] = None
    ) -> Optional[GrantContent]:
        """Extract content from optak.gov.cz grant page"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract metadata from div.item containers
            metadata = self._extract_metadata(soup)

            # Extract other content
            description = self._extract_description(soup)
            funding = self._extract_funding(metadata)
            documents = self._extract_documents(soup, url)
            eligible_recipients = self._extract_eligible_recipients(metadata)

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=grant_metadata.get('title'),
                funding_amounts=funding,
                documents=documents,
                application_url=None,  # Not typically on page
                contact_email=None,
                eligible_recipients=eligible_recipients,
                additional_metadata=metadata,
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

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """Extract metadata from div.item containers"""
        metadata = {}
        
        for item in soup.select('div.item'):
            label_elem = item.select_one('span.text')
            value_elem = item.select_one('div.text_box')
            
            if label_elem and value_elem:
                label = label_elem.get_text(strip=True)
                value = value_elem.get_text(strip=True)
                metadata[label] = value
        
        return metadata

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract description from text_box divs"""
        text_boxes = soup.select('div.text_box')
        if text_boxes:
            paragraphs = []
            for box in text_boxes:
                paras = box.find_all('p')
                if paras:
                    paragraphs.extend([p.get_text(strip=True) for p in paras])
            return '\n\n'.join(paragraphs) if paragraphs else None
        return None

    def _extract_funding(self, metadata: Dict) -> Optional[Dict]:
        """Extract funding from metadata"""
        funding_key = 'Výše dotace'
        if funding_key in metadata:
            text = metadata[funding_key]
            # Pattern: "2 mil. Kč – 60 mil. Kč"
            amounts = re.findall(r'(\d+)\s*mil\.', text)
            if amounts:
                # Convert to CZK
                min_amount = int(amounts[0]) * 1000000 if len(amounts) > 0 else None
                max_amount = int(amounts[-1]) * 1000000 if len(amounts) > 1 else min_amount
                
                result = {'currency': 'CZK'}
                if min_amount:
                    result['min'] = min_amount
                if max_amount:
                    result['max'] = max_amount
                return result
        return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract documents from a.file links"""
        documents = []
        
        for link in soup.select('a.file'):
            href = link.get('href')
            if href:
                title_elem = link.select_one('strong.name')
                title = title_elem.get_text(strip=True) if title_elem else 'Document'
                
                # Get file info
                info_elem = link.select_one('div.file_info span.center_info')
                file_info = info_elem.get_text(strip=True) if info_elem else ''
                
                # Extract format and size
                file_format = 'unknown'
                size = None
                if '(' in file_info:
                    parts = file_info.split('(')
                    if len(parts) >= 2:
                        file_format = parts[0].strip().lower()
                        size = parts[1].strip().rstrip(')')
                
                doc_url = urljoin(base_url, href)
                doc_type = self._classify_document(title)
                
                doc = Document(
                    title=title,
                    url=doc_url,
                    doc_type=doc_type,
                    file_format=file_format,
                    size=size,
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

    def _extract_eligible_recipients(self, metadata: Dict) -> Optional[List[str]]:
        """Extract eligible recipients from metadata"""
        target_key = 'Cílová skupina'
        if target_key in metadata:
            text = metadata[target_key]
            # Split by common delimiters
            recipients = [r.strip() for r in re.split(r'[,;]', text) if r.strip()]
            return recipients if recipients else None
        return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """Download document"""
        return download_document(doc_url, save_path)
