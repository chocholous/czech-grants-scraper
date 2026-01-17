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

from .base import AbstractGrantSubScraper
from .models import GrantContent, Document
from .utils import download_document
from .ai_extractor import extract_grant_details, is_ai_extraction_available

# Configurable constants (can be overridden via ENV vars)
MZ_BASE_URL = os.getenv('MZ_BASE_URL', 'https://mzd.gov.cz')
MZ_CATEGORY_PATH = os.getenv('MZ_CATEGORY_PATH',
                              '/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/')
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))


class MZGovCzScraper(AbstractGrantSubScraper):
    """Scraper for Ministry of Health (MZ) grant calls"""

    # Source identifiers
    SOURCE_ID = "mz-grants"
    SOURCE_NAME = "Ministerstvo zdravotnictví"

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

    def get_source_id(self) -> str:
        """Return source identifier for this scraper"""
        return self.SOURCE_ID

    def get_source_name(self) -> str:
        """Return human-readable source name"""
        return self.SOURCE_NAME

    def get_scraper_name(self) -> str:
        """Return scraper class name for GrantContent"""
        return self.__class__.__name__

    def list_program_urls(self) -> List[str]:
        """
        Scrape category pages and extract all grant call URLs.

        Strategy:
        1. Load main category pages for different years (2025, 2026)
        2. Find all subcategories (grant programs)
        3. For each subcategory, find the main call/announcement page
        4. Return list of call URLs

        Returns:
            List of grant call URLs
        """
        all_call_urls = []

        # Category URLs for different years
        category_urls = [
            urljoin(MZ_BASE_URL, '/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/'),
            urljoin(MZ_BASE_URL, '/category/dotace-a-programove-financovani/narodni-dotacni-programy-pro-rok-2025/'),
        ]

        for category_url in category_urls:
            self.logger.info(f"Processing category: {category_url}")

            try:
                # Find all program subcategories
                subcategories = self._find_subcategories(category_url)
                self.logger.info(f"Found {len(subcategories)} program subcategories")

                # For each subcategory, find the call page
                for subcat_name, subcat_url in subcategories:
                    call_url = self._find_call_page(subcat_url)
                    if call_url:
                        all_call_urls.append(call_url)
                        self.logger.info(f"Found call: {subcat_name} -> {call_url}")
                    else:
                        self.logger.warning(f"No call found for: {subcat_name}")

            except Exception as e:
                self.logger.error(f"Failed to process category {category_url}: {e}")
                continue

        self.logger.info(f"Total calls found: {len(all_call_urls)}")
        return all_call_urls

    def _find_subcategories(self, category_url: str) -> List[tuple]:
        """
        Find all program subcategories within a year category.

        Args:
            category_url: URL of year category (e.g., .../narodni-dotacni-programy-2026/)

        Returns:
            List of (name, url) tuples for each program subcategory
        """
        try:
            response = requests.get(category_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            subcategories = []
            all_links = soup.find_all('a', href=True)

            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)

                # Find links that contain parent category path (subcategories)
                # Extract category slug from URL for matching
                category_parts = urlparse(category_url).path.strip('/').split('/')
                if len(category_parts) > 0:
                    category_slug = category_parts[-1]  # e.g., "narodni-dotacni-programy-2026"

                    # Subcategory must contain parent slug and be different from parent
                    if category_slug in href and href != category_url:
                        # Exclude feeds, tags, etc.
                        if not any(x in href for x in ['/feed', '/tag/', '#', 'javascript']):
                            # Must be category URL
                            if '/category/' in href:
                                subcategories.append((text, href))

            # Deduplicate
            seen = set()
            unique = []
            for name, url in subcategories:
                if url not in seen:
                    seen.add(url)
                    unique.append((name, url))

            return unique

        except Exception as e:
            self.logger.error(f"Failed to find subcategories for {category_url}: {e}")
            return []

    def _find_call_page(self, subcategory_url: str) -> Optional[str]:
        """
        Find the main call/announcement page within a program subcategory.

        Args:
            subcategory_url: URL of program subcategory

        Returns:
            URL of the main call page, or None if not found
        """
        try:
            response = requests.get(subcategory_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Find call pages (výzva keywords)
            call_keywords = ['výzva', 'vyzva', 'žádost', 'zadost', 'vyhlášení', 'vyhlaseni']
            all_links = soup.find_all('a', href=True)

            call_pages = []
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)

                # Look for call keywords in link text
                if any(kw in text.lower() for kw in call_keywords):
                    # Must be absolute mzd.gov.cz URL (not category or other)
                    if 'mzd.gov.cz' in href and href.startswith('http'):
                        # Exclude categories, tags, feeds
                        if not any(x in href for x in ['/category/', '/tag/', '/feed']):
                            call_pages.append((text, href))

            # Deduplicate and return first (usually the main call)
            seen = set()
            for text, url in call_pages:
                if url not in seen:
                    seen.add(url)
                    return url  # Return first unique call

            return None

        except Exception as e:
            self.logger.error(f"Failed to find call page for {subcategory_url}: {e}")
            return None

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """
        Extract full grant content from MZ page.

        Uses AI-powered extraction (Claude Haiku) to enhance regex-based parsing.
        Falls back to regex-only if AI is not available.

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

            # Extract core content (regex-based)
            title = self._extract_title(soup)
            description = self._extract_description(soup)
            summary = self._extract_summary(soup)
            deadline = self._extract_deadline(soup)
            funding_amounts = self._extract_funding_amounts(soup)
            documents = self._extract_documents(soup, url)
            contact_email = self._extract_contact_email(soup)
            eligible_recipients = self._extract_eligible_recipients(soup)

            # AI-enhanced extraction (if API key available)
            if is_ai_extraction_available():
                self.logger.info(f"Using AI extraction for enhanced data quality: {url}")

                # Get clean text for AI
                page_text = soup.get_text(separator='\n', strip=True)

                # Call AI extractor
                ai_data = extract_grant_details(page_text, title or url)

                # Use AI results to fill missing fields or override unreliable regex
                if not deadline and ai_data.get('deadline'):
                    deadline = ai_data['deadline']
                    self.logger.info(f"AI extracted deadline: {deadline}")

                if not eligible_recipients and ai_data.get('eligibility'):
                    eligible_recipients = ai_data['eligibility']
                    self.logger.info(f"AI extracted eligibility: {len(eligible_recipients)} recipients")

                if not funding_amounts and (ai_data.get('funding_min') or ai_data.get('funding_max')):
                    funding_amounts = {
                        'min': ai_data['funding_min'],
                        'max': ai_data['funding_max'],
                        'currency': 'CZK',
                    }
                    self.logger.info(f"AI extracted funding: {funding_amounts}")

                if not summary and ai_data.get('summary'):
                    summary = ai_data['summary']

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
        # Try common content containers (MZ uses wysiwyg-content)
        selectors = [
            '.wysiwyg-content',
            '.entry-content',
            '#content',
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
                for elem in content_elem.find_all(['p']):
                    text = elem.get_text(strip=True)
                    # Filter out short fragments and navigation
                    if text and len(text) > 30:
                        # Skip common non-content patterns
                        if not any(skip in text.lower() for skip in ['menu', 'navigace', 'přeskočit']):
                            text_parts.append(text)

                if text_parts:
                    # Limit to reasonable length (first 5-10 paragraphs)
                    return '\n\n'.join(text_parts[:10])

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
        """
        Extract list of eligible recipients.

        Note: For MZ grants, eligibility info is typically in PDF attachments,
        not on the HTML page. This method returns None for MVP, allowing
        mapper to set appropriate default value and partial status.
        """
        # MZ grants have eligibility info in PDF attachments (Výzva, Metodika)
        # For MVP, we return None and rely on PDF links in attachments
        # Future: Implement PDF parsing to extract eligibility

        # Try to find if there's explicit list on page (rare)
        text = soup.get_text()

        # Only match very specific patterns (avoid false positives)
        # Pattern must have "oprávnění žadatelé:" followed by list
        pattern = r'oprávněn[íý]\s+žadatel[ée]?\s*[:]\s*([^\n]{20,200})'
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            text = match.group(1)
            # Check if it's actually a list (contains commas or separators)
            if ',' in text or ';' in text or ' a ' in text:
                recipients = re.split(r'[,;]|\s+a\s+', text)
                recipients = [r.strip() for r in recipients if r.strip() and len(r.strip()) > 3]
                if recipients:
                    return recipients

        # No eligibility found on HTML page
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
