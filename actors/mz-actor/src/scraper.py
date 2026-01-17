"""
Sub-scraper for mzd.gov.cz (Ministerstvo zdravotnictví).

Extracts grant content from MZ grant pages including:
- Full descriptions and summaries
- Document downloads (PDFs, DOCX)
- Funding amounts and deadlines
- Contact information
"""

import re
import os
from typing import Optional, List, Dict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .scrapers_lib.base import AbstractGrantSubScraper
from .scrapers_lib.models import GrantContent, Document
from .scrapers_lib.utils_simple import download_document

# Configurable constants (can be overridden via ENV vars)
MZ_BASE_URL = os.getenv('MZ_BASE_URL', 'https://mzd.gov.cz')
MZ_CATEGORY_PATH = os.getenv('MZ_CATEGORY_PATH',
                              '/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/')
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))


class MZScraper(AbstractGrantSubScraper):
    """Scraper for Ministry of Health (MZ) grant calls"""

    # Domain identifier for routing
    DOMAIN = "mzd.gov.cz"

    # Document type classification patterns
    DOC_TYPE_PATTERNS = {
        'call_text': ['text', 'znění', 'plné znění', 'vyhlášení'],
        'guidelines': ['příručka', 'guidelines', 'pokyny', 'metodika', 'pravidla'],
        'template': ['vzor', 'template', 'šablona', 'formulář', 'žádost'],
        'budget': ['rozpočet', 'budget', 'kalkulace', 'kalkulačka'],
        'faq': ['faq', 'časté dotazy', 'otázky a odpovědi'],
        'annex': ['příloha', 'annex', 'attachment'],
    }

    def can_handle(self, url: str) -> bool:
        """Check if URL is from mzd.gov.cz domain"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    def list_program_urls(self) -> List[str]:
        """
        Scrape category page and extract all program URLs.

        Returns:
            List of grant program URLs
        """
        category_url = urljoin(MZ_BASE_URL, MZ_CATEGORY_PATH)
        self.logger.info(f"Fetching category page: {category_url}")

        try:
            response = requests.get(category_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract program links
            # Typical WordPress category structure:
            # - .entry-title a
            # - article h2 a
            # - .post-title a
            program_urls = []

            # Try multiple selector patterns
            selectors = [
                'article .entry-title a',
                'article h2 a',
                '.post-title a',
                '.entry-content a',
                'main article a',
            ]

            for selector in selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href:
                        # Filter out non-program links (archives, categories, etc.)
                        if self._is_program_link(href):
                            full_url = urljoin(category_url, href)
                            if full_url not in program_urls:
                                program_urls.append(full_url)

            self.logger.info(f"Found {len(program_urls)} program URLs")
            return program_urls

        except Exception as e:
            self.logger.error(f"Failed to fetch category page: {e}")
            return []

    def _is_program_link(self, href: str) -> bool:
        """Filter out non-program links"""
        # Exclude common non-program paths
        exclude_patterns = [
            '/category/',
            '/tag/',
            '/author/',
            '/page/',
            '/wp-',
            '#',
            'javascript:',
        ]

        for pattern in exclude_patterns:
            if pattern in href:
                return False

        return True

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """
        Extract full grant content from MZ page.

        Args:
            url: Full URL to grant page
            grant_metadata: Metadata (not used for direct scraping)

        Returns:
            GrantContent object with all extracted data
        """
        try:
            # Fetch page HTML
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract core content
            title = self._extract_title(soup)
            description = self._extract_description(soup)
            summary = self._extract_summary(soup)

            # Extract deadline
            deadline = self._extract_deadline(soup)

            # Extract funding amounts
            funding_amounts = self._extract_funding_amounts(soup)

            # Extract documents
            documents = self._extract_documents(soup, url)

            # Extract contact info
            contact_email = self._extract_contact_email(soup)

            # Extract eligible recipients
            eligible_recipients = self._extract_eligible_recipients(soup)

            # Build GrantContent object
            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=summary,
                funding_amounts=funding_amounts,
                documents=documents,
                contact_email=contact_email,
                eligible_recipients=eligible_recipients,
                additional_metadata={
                    'title': title,
                    'deadline': deadline,
                },
            )

            self.logger.info(f"Extracted content from {url}: {len(documents)} documents")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract content from {url}: {e}")
            return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """Download document from MZ to local path"""
        return download_document(doc_url, save_path, timeout=REQUEST_TIMEOUT)

    # ===== Extraction Methods =====

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract grant title from page"""
        # Try common title selectors
        selectors = ['h1', '.entry-title', 'article h1', '.page-title']

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)

        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract full grant description from page.

        Returns the full text content.
        """
        # Try common content containers
        selectors = [
            '.entry-content',
            'article .content',
            'main .content',
            'article',
            'main',
        ]

        for selector in selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Get all text with paragraph separation
                text_parts = []
                for elem in content_elem.find_all(['p', 'div', 'li', 'h1', 'h2', 'h3', 'h4']):
                    text = elem.get_text(strip=True)
                    if text and len(text) > 20:  # Filter out short fragments
                        text_parts.append(text)

                return '\n\n'.join(text_parts) if text_parts else None

        return None

    def _extract_summary(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract short summary from page.

        Usually the first paragraph or intro section.
        """
        # Try intro/perex sections
        intro = soup.select_one('.intro, .perex, .summary, .lead')
        if intro:
            return intro.get_text(strip=True)

        # Fallback: use first paragraph
        first_p = soup.select_one('.entry-content p, article p, main p')
        if first_p:
            text = first_p.get_text(strip=True)
            if len(text) > 50:  # Only use substantial paragraphs
                return text

        return None

    def _extract_deadline(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Parse deadline date from page content.

        Converts Czech date formats to ISO format (YYYY-MM-DD).
        Example: "do 30. 9. 2025" → "2025-09-30"
        """
        text = soup.get_text()

        # Pattern: "do DD. M. YYYY" or "termín: DD. MM. YYYY"
        patterns = [
            r'do\s+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})',
            r'termín[:\s]+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})',
            r'deadline[:\s]+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})',
            r'(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})',  # Generic DD. MM. YYYY
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                day, month, year = match.groups()
                try:
                    # Format as ISO date
                    return f"{year}-{int(month):02d}-{int(day):02d}"
                except ValueError:
                    continue

        return None

    def _extract_funding_amounts(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Extract funding amounts from page content.

        Returns dict with min, max, currency.
        Example: {"min": 0, "max": 100000000, "currency": "CZK"}
        """
        text = soup.get_text()

        # Pattern: "100 000 Kč" or "5 mil. Kč"
        amount_pattern = r'(\d+(?:\s+\d{3})*(?:\s+mil\.)?)\s*(?:Kč|CZK)'
        matches = re.findall(amount_pattern, text)

        if matches:
            # Parse all amounts
            amounts = []
            for match in matches:
                amount = self._parse_czech_amount(match)
                if amount:
                    amounts.append(amount)

            if amounts:
                return {
                    'min': 0,
                    'max': max(amounts),
                    'currency': 'CZK',
                }

        return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """
        Extract documents (PDFs, DOCX) from page.

        Looks for download links with common patterns.
        """
        documents = []

        # Find all links to documents
        doc_links = soup.find_all('a', href=re.compile(r'\.(pdf|docx?|xlsx?|zip)$', re.I))

        for link in doc_links:
            try:
                # Extract URL
                href = link.get('href')
                if not href:
                    continue
                doc_url = urljoin(base_url, href)

                # Extract title (link text or parent text)
                title = link.get_text(strip=True)
                if not title or len(title) < 3:
                    # Try parent element
                    parent = link.find_parent(['li', 'div', 'p'])
                    if parent:
                        title = parent.get_text(strip=True)[:100]  # Truncate long titles

                if not title:
                    title = Path(urlparse(doc_url).path).name

                # Extract file format
                file_format = self._get_file_format(doc_url)

                # Classify document type
                doc_type = self._classify_document_type(title)

                # Create Document object
                doc = Document(
                    title=title,
                    url=doc_url,
                    doc_type=doc_type,
                    file_format=file_format,
                )

                documents.append(doc)

            except Exception as e:
                self.logger.warning(f"Failed to extract document from link: {e}")
                continue

        return documents

    def _extract_contact_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract contact email from page"""
        # Look for mailto links
        email_link = soup.select_one('a[href^="mailto:"]')
        if email_link:
            email = email_link.get('href', '').replace('mailto:', '')
            return email

        # Fallback: search for email pattern in text
        text = soup.get_text()
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        match = re.search(email_pattern, text)
        if match:
            return match.group(0)

        return None

    def _extract_eligible_recipients(self, soup: BeautifulSoup) -> Optional[List[str]]:
        """Extract list of eligible recipients"""
        text = soup.get_text()

        # Look for common patterns
        patterns = [
            r'oprávněn[íý]\s+žadatel[ée]?[:\s]+([^\n\.]+)',
            r'žadatel[ée]?[:\s]+([^\n\.]+)',
            r'eligible\s+applicants[:\s]+([^\n\.]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                text = match.group(1)
                # Split by common separators
                recipients = re.split(r'[,;]|\s+-\s+', text)
                return [r.strip() for r in recipients if r.strip()]

        return None

    # ===== Helper Methods =====

    def _classify_document_type(self, title: str) -> str:
        """
        Classify document based on title keywords.

        Returns: call_text, guidelines, template, budget, faq, annex, other
        """
        title_lower = title.lower()

        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in title_lower:
                    return doc_type

        return 'other'

    def _get_file_format(self, url: str) -> str:
        """
        Extract file format from URL.

        Returns: File extension without dot (e.g., 'pdf', 'xlsx', 'docx')
        """
        path = Path(urlparse(url).path)
        suffix = path.suffix.lower().lstrip('.')
        return suffix if suffix else 'unknown'

    def _parse_czech_amount(self, text: str) -> Optional[int]:
        """
        Parse Czech currency amount to integer.

        Handles formats:
        - "215 000 000 Kč" → 215000000
        - "50 mil. Kč" → 50000000
        - "5,5 mil. Kč" → 5500000
        """
        if not text:
            return None

        # Remove currency symbol
        text = text.replace('Kč', '').replace('CZK', '').strip()

        # Handle millions
        if 'mil.' in text:
            num_str = text.replace('mil.', '').strip()
            num_str = num_str.replace(',', '.').replace(' ', '')
            try:
                num = float(num_str)
                return int(num * 1_000_000)
            except ValueError:
                return None

        # Handle regular numbers with spaces
        num_str = text.replace(' ', '')
        try:
            return int(num_str)
        except ValueError:
            return None
