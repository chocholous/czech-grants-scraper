"""
Sub-scraper for opst.cz (OP Spravedlivá transformace / Just Transition Fund).

Extracts full grant content from opst.cz grant pages including:
- Full descriptions and summaries
- Document downloads (PDFs, XLSX, DOCX)
- Funding amounts
- Application portals
- Contact information
"""

import re
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import AbstractGrantSubScraper
from .models import GrantContent, Document
from .utils import download_document, convert_document_to_markdown


class OPSTCzScraper(AbstractGrantSubScraper):
    """Scraper for opst.cz grant calls"""

    # Domain identifier for routing
    DOMAIN = "opst.cz"

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
        """Check if URL is from opst.cz domain"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """
        Extract full grant content from opst.cz page.

        Args:
            url: Full URL to grant page (e.g., https://opst.cz/dotace/101-vyzva/)
            grant_metadata: Metadata from dotaceeu.cz (title, call_number, etc.)

        Returns:
            GrantContent object with all extracted data
        """
        try:
            # Fetch page HTML
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract metadata from call-card rows
            metadata = self._extract_metadata(soup)

            # Extract description
            description = self._extract_description(soup)
            summary = self._extract_summary(soup)

            # Extract funding amounts
            funding_amounts = self._extract_funding_amounts(soup, metadata)

            # Extract documents
            documents = self._extract_documents(soup, url)

            # Extract application URL
            application_url = self._extract_application_url(soup)

            # Extract contact email
            contact_email = self._extract_contact_email(soup)

            # Extract eligible recipients
            eligible_recipients = self._extract_eligible_recipients(soup, metadata)

            # Build GrantContent object
            content = GrantContent(
                source_url=url,
                scraper_name=self.get_scraper_name(),
                scraped_at=datetime.now(timezone.utc),
                description=description,
                summary=summary,
                funding_amounts=funding_amounts,
                documents=documents,
                application_url=application_url,
                contact_email=contact_email,
                eligible_recipients=eligible_recipients,
                additional_metadata=metadata,
            )

            self.logger.info(f"Extracted content from {url}: {len(documents)} documents, "
                           f"{len(description or '')} chars description")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract content from {url}: {e}")
            return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """Download document from opst.cz to local path"""
        return download_document(doc_url, save_path)

    # ===== Extraction Methods =====

    def _extract_metadata(self, soup: BeautifulSoup) -> dict:
        """
        Extract metadata from .call-card__row elements.

        Example HTML:
        <div class="call-card__row">
            <div class="call-card__label">Stav výzvy:</div>
            <div class="call-card__value">Otevřená</div>
        </div>
        """
        metadata = {}

        for row in soup.select('.call-card__row'):
            label_elem = row.select_one('.call-card__label')
            value_elem = row.select_one('.call-card__value')

            if label_elem and value_elem:
                label = label_elem.get_text(strip=True).rstrip(':')
                value = value_elem.get_text(strip=True)
                metadata[label] = value

        return metadata

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract full grant description from .call__content section.

        Returns the full HTML content converted to markdown-like text.
        """
        content_elem = soup.select_one('.call__content')
        if not content_elem:
            return None

        # Get all text with paragraph separation
        text_parts = []
        for elem in content_elem.find_all(['p', 'div', 'li', 'h1', 'h2', 'h3', 'h4']):
            text = elem.get_text(strip=True)
            if text:
                text_parts.append(text)

        return '\n\n'.join(text_parts) if text_parts else None

    def _extract_summary(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract short summary/perex from page.

        Usually the first paragraph or intro section.
        """
        # Try to find intro/perex section
        intro = soup.select_one('.call__intro, .perex, .summary')
        if intro:
            return intro.get_text(strip=True)

        # Fallback: use first paragraph from description
        first_p = soup.select_one('.call__content p')
        if first_p:
            return first_p.get_text(strip=True)

        return None

    def _extract_funding_amounts(self, soup: BeautifulSoup, metadata: dict) -> Optional[dict]:
        """
        Extract funding amounts from metadata or page content.

        Returns dict with total, min, max, currency.
        Example: {"total": 215000000, "currency": "CZK"}
        """
        # Check metadata fields
        funding_fields = [
            'Celková alokace',
            'Alokace výzvy',
            'Rozpočet',
            'Dotace',
        ]

        for field in funding_fields:
            if field in metadata:
                amount = self._parse_czech_amount(metadata[field])
                if amount:
                    return {
                        'total': amount,
                        'currency': 'CZK',
                        'source': field,
                    }

        # Fallback: search in page text
        text = soup.get_text()
        # Pattern: "215 000 000 Kč" or "215 mil. Kč"
        amount_pattern = r'(\d+(?:\s+\d{3})*(?:\s+mil\.)?)\s*Kč'
        matches = re.findall(amount_pattern, text)

        if matches:
            # Take the largest amount (likely total allocation)
            amounts = [self._parse_czech_amount(m) for m in matches]
            amounts = [a for a in amounts if a]  # Filter None values

            if amounts:
                return {
                    'total': max(amounts),
                    'currency': 'CZK',
                    'source': 'page_text',
                }

        return None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """
        Extract documents from .dms__item elements.

        Example HTML:
        <div class="dms__item">
            <a class="dms__download" href="/media/..." download>
                <span class="dms__title">Text výzvy</span>
            </a>
            <div class="dms__meta">
                <span class="dms__size">
                    <span>165.03</span>
                    <span>kB</span>
                </span>
                <span class="dms__date">Platnost: 18. 12. 2025</span>
            </div>
        </div>
        """
        documents = []

        for item in soup.select('.dms__item'):
            try:
                # Extract title
                title_elem = item.select_one('.dms__title')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)

                # Extract URL
                link_elem = item.select_one('a.dms__download[download]')
                if not link_elem or not link_elem.get('href'):
                    continue
                doc_url = urljoin(base_url, link_elem['href'])

                # Extract file format from URL
                file_format = self._get_file_format(doc_url)

                # Extract size
                size = None
                size_elem = item.select_one('.dms__size')
                if size_elem:
                    size_parts = [s.get_text(strip=True) for s in size_elem.find_all('span')]
                    size = ' '.join(size_parts) if size_parts else None

                # Extract validity date
                validity_date = None
                date_elem = item.select_one('.dms__date')
                if date_elem:
                    validity_date = date_elem.get_text(strip=True)

                # Classify document type
                doc_type = self._classify_document_type(title)

                # Create Document object
                doc = Document(
                    title=title,
                    url=doc_url,
                    doc_type=doc_type,
                    file_format=file_format,
                    size=size,
                    validity_date=validity_date,
                )

                documents.append(doc)

            except Exception as e:
                self.logger.warning(f"Failed to extract document from item: {e}")
                continue

        return documents

    def _extract_application_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract application portal URL"""
        # Look for application portal links
        portal_link = soup.select_one('a[href*="portal"], a[href*="aplikace"], a.application-link')
        if portal_link and portal_link.get('href'):
            return portal_link['href']

        return None

    def _extract_contact_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract contact email from page"""
        # Look for email addresses in mailto links
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

    def _extract_eligible_recipients(self, soup: BeautifulSoup, metadata: dict) -> Optional[List[str]]:
        """Extract list of eligible recipients"""
        # Check metadata
        if 'Oprávnění žadatelé' in metadata:
            text = metadata['Oprávnění žadatelé']
            # Split by common separators
            recipients = re.split(r'[,;]|\s+-\s+', text)
            return [r.strip() for r in recipients if r.strip()]

        return None

    # ===== Helper Methods =====

    def _classify_document_type(self, title: str) -> str:
        """
        Classify document based on title keywords.

        Args:
            title: Document title (e.g., "Text výzvy", "Příručka pro žadatele")

        Returns:
            Document type: call_text, guidelines, template, budget, faq, annex, other
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

        Args:
            url: Document URL

        Returns:
            File extension without dot (e.g., 'pdf', 'xlsx', 'docx')
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

        Args:
            text: Amount text in Czech format

        Returns:
            Amount as integer or None if parsing failed
        """
        if not text:
            return None

        # Remove currency symbol
        text = text.replace('Kč', '').strip()

        # Handle millions
        if 'mil.' in text:
            # Extract number before "mil."
            num_str = text.replace('mil.', '').strip()
            # Replace comma with dot for float parsing
            num_str = num_str.replace(',', '.').replace(' ', '')
            try:
                num = float(num_str)
                return int(num * 1_000_000)
            except ValueError:
                return None

        # Handle regular numbers with spaces
        # "215 000 000" → "215000000"
        num_str = text.replace(' ', '')
        try:
            return int(num_str)
        except ValueError:
            return None
