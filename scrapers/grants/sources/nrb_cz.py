"""
Sub-scraper for nrb.cz and nrinvesticni.cz (National Development Bank).

Extracts loan and investment financial instruments with grant components.
Handles multiple operational programmes (OP ST, OP TAK, NPO, Modernizační fond).
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
from .utils import download_document


class NRBCzScraper(AbstractGrantSubScraper):
    """Scraper for nrb.cz and nrinvesticni.cz financial instruments"""

    DOMAINS = ["nrb.cz", "nrinvesticni.cz"]

    # Programme identification patterns (priority order)
    PROGRAMME_PATTERNS = {
        'OP ST': ['op st', 'spravedlivá transformace', 'spravedliva transformace', 'just transition'],
        'OP TAK': ['op tak', 'technologie a aplikace', 'technologie'],
        'NPO': ['npo', 'národní plán obnovy', 'narodni plan obnovy', 'recovery plan'],
        'Modernizační fond': ['modernizační fond', 'modernizacni fond'],
    }

    # Document type patterns
    DOC_TYPE_PATTERNS = {
        'call_text': ['výzva', 'vyzva', 'call'],
        'application': ['žádost', 'zadost', 'application', 'formulář'],
        'guidelines': ['pokyny', 'metodika', 'guidelines', 'příručka'],
        'annex': ['příloha', 'priloha', 'annex', 'attachment'],
    }

    def can_handle(self, url: str) -> bool:
        """Check if URL is from nrb.cz or nrinvesticni.cz"""
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in self.DOMAINS)

    async def extract_content(
        self, url: str, grant_metadata: dict, use_llm: Optional[bool] = None
    ) -> Optional[GrantContent]:
        """Extract content from nrb.cz/nrinvesticni.cz page"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else grant_metadata.get('title', '')

            # Extract description
            description = self._extract_description(soup)

            # Classify operational programme
            programme = self._classify_programme(soup, url)

            # Extract financial parameters
            financial_params = self._extract_financial_parameters(soup, programme)

            # Detect suspension status
            is_suspended = self._detect_suspension(soup)

            # Extract documents
            documents = self._extract_documents(soup, url)

            # Extract contact email (if not obfuscated)
            contact_email = self._extract_contact_email(soup)

            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=title,
                funding_amounts=financial_params,  # Extended dict with loan parameters
                documents=documents,
                application_url=self._find_application_url(soup, url),
                contact_email=contact_email,
                eligible_recipients=None,  # Text-based, defer to phase 2
                additional_metadata={
                    'programme': programme,
                    'is_suspended': is_suspended,
                    'source_domain': urlparse(url).netloc,
                    'instrument_type': self._classify_instrument_type(title, description),
                }
            )

            self.logger.info(f"Extracted content from {url} - Programme: {programme}, Suspended: {is_suspended}")

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
        """Extract main content description"""
        # WordPress content area
        content_div = soup.find('div', class_=['entry-content', 'product-content', 'content'])
        if content_div:
            # Get first few paragraphs
            paragraphs = content_div.find_all('p', limit=5)
            description = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            return description if description else None
        return None

    def _classify_programme(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """
        Classify operational programme using pattern matching.

        Priority order:
        1. Breadcrumbs
        2. Title and description
        3. Full page text
        """
        # Get all text content
        page_text = soup.get_text().lower()

        # Check breadcrumbs first (most reliable)
        breadcrumbs = soup.find('nav', class_='breadcrumb')
        if breadcrumbs:
            breadcrumb_text = breadcrumbs.get_text().lower()
            for programme, patterns in self.PROGRAMME_PATTERNS.items():
                if any(pattern in breadcrumb_text for pattern in patterns):
                    return programme

        # Check title and description
        title = soup.find('h1')
        if title:
            title_text = title.get_text().lower()
            for programme, patterns in self.PROGRAMME_PATTERNS.items():
                if any(pattern in title_text for pattern in patterns):
                    return programme

        # Check full page text
        for programme, patterns in self.PROGRAMME_PATTERNS.items():
            if any(pattern in page_text for pattern in patterns):
                return programme

        return None

    def _extract_financial_parameters(self, soup: BeautifulSoup, programme: Optional[str]) -> Optional[Dict]:
        """
        Extract loan parameters from unstructured text.

        Returns extended funding_amounts dict with loan-specific fields.
        """
        text = soup.get_text()
        params = {
            'type': 'loan',  # vs 'grant' for traditional grants
        }

        # Extract loan amount (min/max)
        # Pattern: "od 500 tis. Kč" or "do 50 mil. Kč" or "500 000 – 10 000 000 Kč"

        # Min amount
        min_patterns = [
            r'(?:minimální|od)\s+(?:částka|výše)?\s*(\d+(?:\s*\d{3})*)\s*(?:tis\.|mil\.|mld\.)?\s*Kč',
            r'(\d+(?:\s*\d{3})*)\s*(?:tis\.|mil\.)\s*Kč\s*(?:minimálně|nejméně)',
        ]
        for pattern in min_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(' ', '')
                multiplier = self._get_multiplier(match.group(0))
                params['loan_amount_min'] = int(amount_str) * multiplier
                break

        # Max amount
        max_patterns = [
            r'(?:maximální|do|až)\s+(?:částka|výše)?\s*(\d+(?:\s*\d{3})*)\s*(?:tis\.|mil\.|mld\.)?\s*Kč',
            r'(\d+(?:\s*\d{3})*)\s*(?:tis\.|mil\.)\s*Kč\s*(?:maximálně|nejvýše)',
        ]
        for pattern in max_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(' ', '')
                multiplier = self._get_multiplier(match.group(0))
                params['loan_amount_max'] = int(amount_str) * multiplier
                break

        # Extract interest rate
        # Pattern: "0 %", "3 % p.a.", "úroková sazba 2,5 %"
        rate_match = re.search(r'(?:úroková sazba|úrok|interest rate)?\s*(\d+(?:[.,]\d+)?)\s*%', text, re.IGNORECASE)
        if rate_match:
            rate_str = rate_match.group(1).replace(',', '.')
            params['interest_rate'] = float(rate_str)

        # Extract loan term
        # Pattern: "splatnost 15 let", "doba trvání 10 – 25 let"
        term_match = re.search(r'(?:splatnost|doba trvání|term)?\s*(\d+)(?:\s*[–-]\s*(\d+))?\s*let', text, re.IGNORECASE)
        if term_match:
            params['term_years_min'] = int(term_match.group(1))
            if term_match.group(2):
                params['term_years_max'] = int(term_match.group(2))
            else:
                params['term_years_max'] = params['term_years_min']

        # Extract grant component
        # Pattern: "dotace 30 %", "grant 50 %", "nenávratná část 40 %"
        grant_match = re.search(r'(?:dotace|grant|nenávratná část|podpora)?\s*(\d+)\s*%', text, re.IGNORECASE)
        if grant_match:
            params['grant_component_percent'] = int(grant_match.group(1))

        return params if len(params) > 1 else None  # Return None if only 'type' field

    def _get_multiplier(self, text: str) -> int:
        """Get multiplier from Czech abbreviations"""
        if 'tis.' in text.lower():
            return 1_000
        elif 'mil.' in text.lower():
            return 1_000_000
        elif 'mld.' in text.lower():
            return 1_000_000_000
        return 1

    def _detect_suspension(self, soup: BeautifulSoup) -> bool:
        """Detect if programme is suspended"""
        text = soup.get_text().lower()
        suspension_keywords = [
            'pozastaveno',
            'pozastavená',
            'suspended',
            'ukončeno',
            'uzavřeno',
            'nepříjímá',
            'neprijima',
        ]
        return any(keyword in text for keyword in suspension_keywords)

    def _classify_instrument_type(self, title: str, description: Optional[str]) -> str:
        """Classify type of financial instrument"""
        text = (title + ' ' + (description or '')).lower()

        if 'záruka' in text or 'guarantee' in text:
            return 'guarantee'
        elif 'kapitál' in text or 'equity' in text or 'podíl' in text:
            return 'equity'
        elif 'úvěr' in text or 'loan' in text or 'půjčka' in text:
            return 'loan'
        else:
            return 'hybrid'  # Loan + grant combination

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract document links from page"""
        documents = []

        # Find all links to WordPress uploads or PDF files
        for link in soup.find_all('a', href=True):
            href = link['href']

            # Skip non-document links
            if not any(ext in href.lower() for ext in ['.pdf', '.xlsx', '.xlsm', '.docx', '.zip', '/wp-content/uploads/']):
                continue

            try:
                doc_title = link.get_text(strip=True) or link.get('title', Path(href).name)
                doc_url = urljoin(base_url, href)

                # Get file format
                path = Path(urlparse(doc_url).path)
                file_format = path.suffix.lstrip('.').lower()

                # Classify document type
                doc_type = self._classify_document_type(doc_title)

                doc = Document(
                    title=doc_title,
                    url=doc_url,
                    doc_type=doc_type,
                    file_format=file_format,
                    size=None,  # Not typically shown on page
                    validity_date=None
                )

                documents.append(doc)

            except Exception as e:
                self.logger.warning(f"Failed to extract document from {href}: {e}")
                continue

        return documents

    def _classify_document_type(self, title: str) -> str:
        """Classify document based on title"""
        title_lower = title.lower()

        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(pattern in title_lower for pattern in patterns):
                return doc_type

        return 'other'

    def _find_application_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Find application form/portal URL"""
        # Look for links containing "zadost" or "application"
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().lower()

            if any(keyword in href.lower() or keyword in text for keyword in ['zadost', 'application', 'formular']):
                return urljoin(base_url, href)

        return None

    def _extract_contact_email(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract contact email (if not Cloudflare-obfuscated).

        Note: Many emails are obfuscated. Return None rather than trying to decode.
        """
        # Simple email regex for non-obfuscated emails
        text = soup.get_text()
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            return email_match.group(0)
        return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """Download document from nrb.cz WordPress uploads"""
        return download_document(doc_url, save_path)
