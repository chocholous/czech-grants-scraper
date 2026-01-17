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

        MZD uses 3-level structure:
        1. Root category → Sub-categories
        2. Sub-categories → Article detail pages

        Returns:
            List of grant program detail page URLs
        """
        root_url = urljoin(MZ_BASE_URL, MZ_CATEGORY_PATH)
        self.logger.info(f"Fetching root category: {root_url}")

        all_article_urls = []

        try:
            # LEVEL 1: Get sub-categories from root
            sub_categories = self._get_sub_categories(root_url)
            self.logger.info(f"Found {len(sub_categories)} sub-categories")

            # LEVEL 2: Get article URLs from each sub-category
            for sub_cat_url in sub_categories:
                try:
                    article_urls = self._get_articles_from_category(sub_cat_url)
                    self.logger.info(f"Found {len(article_urls)} articles in {sub_cat_url}")
                    all_article_urls.extend(article_urls)
                except Exception as e:
                    self.logger.error(f"Failed to scrape sub-category {sub_cat_url}: {e}")
                    continue

            # Deduplicate
            all_article_urls = list(set(all_article_urls))
            self.logger.info(f"Total unique article URLs: {len(all_article_urls)}")
            return all_article_urls

        except Exception as e:
            self.logger.error(f"Failed to fetch root category: {e}")
            return []

    def _get_sub_categories(self, root_url: str) -> List[str]:
        """
        Get sub-category URLs from root category page.

        Sub-categories are /category/ links that contain the root path.
        """
        response = requests.get(root_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find main content area
        main = soup.find('main')
        if not main:
            main = soup

        sub_categories = []
        for link in main.find_all('a', href=True):
            href = link.get('href')
            text = link.get_text(strip=True)

            # Sub-categories contain root path + additional segment
            if MZ_CATEGORY_PATH in href and len(text) > 10:
                full_url = urljoin(root_url, href)
                # Not the root itself
                if full_url != root_url and full_url not in sub_categories:
                    sub_categories.append(full_url)

        return sub_categories

    def _get_articles_from_category(self, category_url: str) -> List[str]:
        """
        Get article detail page URLs from a category page.

        Articles have structure: <h2 class="article-name"><a class="text-decoration-hover">
        """
        response = requests.get(category_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        article_urls = []

        # Method 1: h2.article-name a.text-decoration-hover (primary)
        article_headings = soup.select('h2.article-name a.text-decoration-hover')
        for link in article_headings:
            href = link.get('href')
            if href:
                full_url = urljoin(category_url, href)
                if full_url not in article_urls:
                    article_urls.append(full_url)

        # Method 2: Fallback - any a.text-decoration-hover (excluding categories)
        if not article_urls:
            main = soup.find('main') or soup
            for link in main.find_all('a', class_='text-decoration-hover'):
                href = link.get('href')
                if href and '/category/' not in href:
                    full_url = urljoin(category_url, href)
                    if full_url not in article_urls:
                        article_urls.append(full_url)

        return article_urls

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
        # Method 1: Try meta description (most reliable for MZD)
        meta_desc = soup.find('meta', {'property': 'og:description'}) or \
                    soup.find('meta', {'name': 'description'})
        if meta_desc:
            content = meta_desc.get('content', '').strip()
            if len(content) > 50:
                return content

        # Method 2: First paragraph in main content
        main = soup.find('main')
        if main:
            first_p = main.find('p')
            if first_p:
                text = first_p.get_text(strip=True)
                if len(text) > 50:
                    return text

        # Method 3: All paragraphs in entry-content
        content_elem = soup.select_one('.entry-content, article')
        if content_elem:
            paragraphs = content_elem.find_all('p', limit=3)  # First 3 paragraphs
            text_parts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
            if text_parts:
                return '\n\n'.join(text_parts)

        return None

    def _extract_summary(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract short summary from page.

        Returns first sentence or short description (max 300 chars).
        """
        # Try meta description (truncated to first sentence)
        meta_desc = soup.find('meta', {'property': 'og:description'}) or \
                    soup.find('meta', {'name': 'description'})
        if meta_desc:
            content = meta_desc.get('content', '').strip()
            if content:
                # Take first sentence
                first_sentence = content.split('.')[0] + '.' if '.' in content else content
                return first_sentence[:300]  # Max 300 chars

        # Fallback: first paragraph
        main = soup.find('main')
        if main:
            first_p = main.find('p')
            if first_p:
                text = first_p.get_text(strip=True)
                if len(text) > 50:
                    # Take first sentence
                    first_sentence = text.split('.')[0] + '.' if '.' in text else text
                    return first_sentence[:300]

        return None

    def _extract_deadline(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Parse deadline date from page content.

        Converts Czech date formats to ISO format (YYYY-MM-DD).
        Example: "do 30. září 2025" → "2025-09-30"
        """
        # First, try meta description (most reliable for MZD)
        meta_desc = soup.find('meta', {'property': 'og:description'}) or \
                    soup.find('meta', {'name': 'description'})
        if meta_desc:
            meta_text = meta_desc.get('content', '')
            deadline = self._parse_deadline_from_text(meta_text)
            if deadline:
                return deadline

        # Fallback: search full page text
        text = soup.get_text()
        return self._parse_deadline_from_text(text)

    def _parse_deadline_from_text(self, text: str) -> Optional[str]:
        """
        Parse deadline from text using various patterns.

        Prefers patterns with "do" keyword (submission deadline).
        """
        # Priority patterns (submission deadlines)
        priority_patterns = [
            r'do\s+(\d{1,2})\.\s*(\w+)\s+(\d{4})',  # "do 30. září 2025"
            r'do\s+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})',  # "do 30. 9. 2025"
            r'termín.*?do\s+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})',
        ]

        for pattern in priority_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._format_date_match(match.groups())

        # Fallback patterns (generic dates)
        fallback_patterns = [
            r'termín[:\s]+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})',
            r'deadline[:\s]+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})',
        ]

        for pattern in fallback_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._format_date_match(match.groups())

        return None

    def _format_date_match(self, groups: tuple) -> Optional[str]:
        """Format matched date groups to YYYY-MM-DD"""
        if len(groups) == 3:
            day, month, year = groups

            # Convert Czech month names to numbers
            czech_months = {
                'ledna': '01', 'února': '02', 'března': '03', 'dubna': '04',
                'května': '05', 'června': '06', 'července': '07', 'srpna': '08',
                'září': '09', 'října': '10', 'listopadu': '11', 'prosince': '12',
            }

            # Check if month is a word
            month_lower = month.lower()
            if month_lower in czech_months:
                month = czech_months[month_lower]

            try:
                # Format as ISO date
                return f"{year}-{int(month):02d}-{int(day):02d}"
            except ValueError:
                pass

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
        # Try meta description first (often contains eligibility info)
        meta_desc = soup.find('meta', {'property': 'og:description'}) or \
                    soup.find('meta', {'name': 'description'})
        if meta_desc:
            meta_text = meta_desc.get('content', '')
            recipients = self._parse_recipients_from_text(meta_text)
            if recipients:
                return recipients

        # Fallback: search in main content
        main = soup.find('main')
        if main:
            # Look in lists first (most structured)
            for ul in main.find_all('ul', limit=3):
                items = [li.get_text(strip=True) for li in ul.find_all('li')[:10]]
                # Check if looks like recipients list (not too long items)
                if items and all(len(item) < 150 for item in items):
                    if any(keyword in ' '.join(items).lower()
                           for keyword in ['žadatel', 'organizace', 'subjekt', 'poskytovatel']):
                        return items[:10]  # Max 10 recipients

        # Last resort: parse from full text
        text = soup.get_text()
        return self._parse_recipients_from_text(text)

    def _parse_recipients_from_text(self, text: str) -> Optional[List[str]]:
        """Parse eligible recipients from text using patterns"""
        # Look for common patterns
        patterns = [
            r'oprávněn[íý]\s+žadatel[ée]?[:\s]+([^\.]{10,200})',  # Limit to 200 chars
            r'cílová skupina[:\s]+([^\.]{10,200})',
            r'žadatel[ée]?\s+mohou být[:\s]+([^\.]{10,200})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                matched_text = match.group(1).strip()
                # Split by common separators
                recipients = re.split(r'[,;]|\s+-\s+|\s+a\s+', matched_text)
                # Clean and filter
                cleaned = [r.strip() for r in recipients if r.strip() and len(r.strip()) > 3]
                if cleaned:
                    return cleaned[:10]  # Max 10

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
