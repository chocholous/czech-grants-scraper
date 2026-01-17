"""
Sub-scraper for SZIF MZe National Grants (szif.gov.cz).

Autonomous scraper that:
1. Starts from root URL (https://szif.gov.cz/cs/narodni-dotace)
2. Discovers all grant programs
3. Downloads and parses PDF Zásady document
4. Extracts detailed content for each program and sub-program
5. Creates GrantContent with structured data
"""

import re
import os
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import AbstractGrantSubScraper
from .models import GrantContent, Document
from .utils import download_document
from .pdf_zasady_parser import ZasadyPDFParser


class MZeSZIFCzScraper(AbstractGrantSubScraper):
    """
    Autonomous scraper for MZe national grants administered by SZIF.

    Handles:
    - HTML program list extraction
    - PDF Zásady download and parsing
    - Structured data extraction (amounts, deadlines, eligibility)
    - Sub-program discovery (e.g., 20.A → 20.A.a, 20.A.b, 20.A.c)
    """

    # Domain identifier
    DOMAINS = ["szif.gov.cz", "szif.cz"]

    # Root URLs
    ROOT_URL = "https://szif.gov.cz/cs/narodni-dotace"
    PROGRAMS_LIST_URL = "https://szif.gov.cz/cs/nd-dotacni-programy"

    # Document classification
    DOC_TYPE_PATTERNS = {
        'call_text': ['zásady', 'pravidla', 'podmínky'],
        'guidelines': ['příručka', 'pokyny', 'metodika'],
        'info': ['informace', 'sdělení'],
        'template': ['vzor', 'formulář', 'šablona'],
    }

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self._pdf_parser = None
        self._pdf_cache_path = None

    def can_handle(self, url: str) -> bool:
        """Check if URL is from SZIF domain"""
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in self.DOMAINS)

    async def extract_content(self, url: str, grant_metadata: dict) -> Optional[GrantContent]:
        """
        Extract content for a single grant program URL.

        This is called by the orchestrator for each discovered grant URL.

        Args:
            url: URL to grant detail page (e.g., https://szif.gov.cz/cs/nd-dotacni-programy-18)
            grant_metadata: Metadata from discovery phase

        Returns:
            GrantContent with all extracted data
        """
        try:
            # Extract program ID from URL
            match = re.search(r'/nd-dotacni-programy-([\w\-]+)$', url)
            if not match:
                self.logger.warning(f"Could not extract program ID from URL: {url}")
                return None

            program_id = match.group(1).upper()

            # Get HTML detail
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            # Extract HTML metadata
            html_data = self._extract_html_data(soup, url)

            # Get PDF data for this program
            pdf_data = await self._get_pdf_data_for_program(program_id)

            # Combine data
            content = self._build_grant_content(
                program_id=program_id,
                url=url,
                html_data=html_data,
                pdf_data=pdf_data,
            )

            self.logger.info(f"Extracted content for program {program_id}: {content.description[:50] if content.description else 'N/A'}...")
            return content

        except Exception as e:
            self.logger.error(f"Failed to extract content from {url}: {e}")
            return None

    async def scrape_all_programs(self, year: int = 2026) -> List[GrantContent]:
        """
        AUTONOMOUS SCRAPING: Start from root, discover and scrape all programs.

        This is the main entry point for autonomous operation.

        Args:
            year: Year to scrape (for PDF Zásady)

        Returns:
            List of GrantContent for all discovered programs
        """
        self.logger.info(f"Starting autonomous scrape of MZe grants for year {year}")

        # Step 1: Discover all programs from HTML
        programs = self._discover_all_programs()
        self.logger.info(f"Discovered {len(programs)} programs")

        # Step 2: Download and parse PDF Zásady
        pdf_path = await self._download_zasady_pdf(year)
        if pdf_path:
            self._parse_zasady_pdf(pdf_path)
            self.logger.info(f"Parsed PDF with {len(self._pdf_parser.programs) if self._pdf_parser else 0} programs")

        # Step 3: Extract content for each program
        all_content = []
        for i, prog in enumerate(programs, 1):
            self.logger.info(f"[{i}/{len(programs)}] Processing {prog['program_id']}...")

            content = await self.extract_content(prog['program_url'], prog)
            if content:
                all_content.append(content)

        self.logger.info(f"Successfully scraped {len(all_content)} programs")
        return all_content

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """Download document from SZIF"""
        return download_document(doc_url, save_path)

    # ===== Discovery Methods =====

    def _discover_all_programs(self) -> List[dict]:
        """
        Discover all grant programs from programs list page.

        Returns:
            List of dicts with program_id, program_url, name
        """
        response = self.session.get(self.PROGRAMS_LIST_URL, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')

        programs = []

        # Find all program links
        program_links = soup.find_all('a', href=re.compile(r'/cs/nd-dotacni-programy-[\w\-]+'))

        seen_ids = set()
        for link in program_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)

            match = re.search(r'/cs/nd-dotacni-programy-([\w\-]+)', href)
            if match:
                program_id = match.group(1).upper()

                # Deduplicate
                if program_id in seen_ids:
                    continue
                seen_ids.add(program_id)

                programs.append({
                    'program_id': program_id,
                    'program_url': f"https://szif.gov.cz{href}",
                    'name': text
                })

        return programs

    # ===== HTML Extraction Methods =====

    def _extract_html_data(self, soup: BeautifulSoup, url: str) -> dict:
        """Extract data from HTML program detail page"""
        data = {
            'description': self._extract_description(soup),
            'news': self._extract_news(soup),
            'documents': self._extract_documents(soup, url),
        }
        return data

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract short description from HTML"""
        desc_div = soup.find('div', class_='section')
        if desc_div:
            # Get text after H2
            h2 = desc_div.find('h2')
            if h2:
                text_parts = []
                for sibling in h2.find_next_siblings():
                    if sibling.name == 'div' and 'section' in sibling.get('class', []):
                        break
                    text_parts.append(sibling.get_text(strip=True))
                return ' '.join(text_parts)
        return None

    def _extract_news(self, soup: BeautifulSoup) -> List[dict]:
        """Extract news/announcements"""
        news = []
        news_section = soup.find('div', class_='section news')
        if news_section:
            for item in news_section.find_all('li', class_='file'):
                h4 = item.find('h4')
                meta = item.find('div', class_='meta')
                link = item.find('a')

                if h4 and link:
                    news.append({
                        'title': h4.get_text(strip=True),
                        'date': meta.get_text(strip=True) if meta else '',
                        'url': urljoin('https://szif.gov.cz', link.get('href', ''))
                    })
        return news

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        """Extract document links from HTML"""
        documents = []
        docs_section = soup.find('div', class_='section documents')

        if docs_section:
            doc_links = docs_section.find_all('a', href=re.compile(r'\.pdf'))
            for link in doc_links:
                href = link.get('href', '')
                if href.startswith('/cs/CmDocument'):
                    title = link.get_text(strip=True)
                    url = urljoin('https://szif.gov.cz', href)
                    doc_type = self._classify_document_type(title)

                    documents.append(Document(
                        title=title,
                        url=url,
                        doc_type=doc_type,
                        file_format='pdf',
                    ))

        return documents

    def _classify_document_type(self, title: str) -> str:
        """Classify document by title"""
        title_lower = title.lower()

        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(pattern in title_lower for pattern in patterns):
                return doc_type

        return 'other'

    # ===== PDF Methods =====

    async def _download_zasady_pdf(self, year: int) -> Optional[str]:
        """
        Download Zásady PDF for given year.

        Returns:
            Path to downloaded PDF or None
        """
        # First, find the PDF URL from main page
        pdf_url = self._find_zasady_pdf_url(year)

        if not pdf_url:
            self.logger.warning(f"Could not find Zásady PDF URL for year {year}")
            return None

        # Download
        cache_dir = Path('data')
        cache_dir.mkdir(exist_ok=True)
        pdf_path = cache_dir / f'zasady_{year}.pdf'

        if pdf_path.exists():
            self.logger.info(f"Using cached PDF: {pdf_path}")
            self._pdf_cache_path = str(pdf_path)
            return str(pdf_path)

        try:
            self.logger.info(f"Downloading Zásady PDF from {pdf_url}...")
            response = self.session.get(pdf_url, timeout=30, stream=True)
            response.raise_for_status()

            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.logger.info(f"Downloaded to {pdf_path}")
            self._pdf_cache_path = str(pdf_path)
            return str(pdf_path)

        except Exception as e:
            self.logger.error(f"Failed to download PDF: {e}")
            return None

    def _find_zasady_pdf_url(self, year: int) -> Optional[str]:
        """Find Zásady PDF URL from main page or programs page"""
        # Try finding from main narodni-dotace page
        try:
            response = self.session.get(self.ROOT_URL, timeout=10)
            soup = BeautifulSoup(response.content, 'lxml')

            # Look for link containing "Zásady" and year
            for link in soup.find_all('a', href=re.compile(r'CmDocument.*\.pdf')):
                text = link.get_text(strip=True)
                if 'zásady' in text.lower() and str(year) in text:
                    return urljoin('https://szif.gov.cz', link['href'])

        except Exception as e:
            self.logger.warning(f"Could not find PDF URL: {e}")

        # Fallback: use known pattern (may need manual update)
        return f"https://szif.gov.cz/cs/CmDocument?rid=%2Fapa_anon%2Fcs%2Fdokumenty_ke_stazeni%2Fnarodni_dotace%2F{year}.pdf"

    def _parse_zasady_pdf(self, pdf_path: str):
        """Parse Zásady PDF using enhanced parser"""
        self._pdf_parser = ZasadyPDFParser(pdf_path)
        self._pdf_parser.extract_text()
        self._pdf_parser.parse_programs()

    async def _get_pdf_data_for_program(self, program_id: str) -> Optional[dict]:
        """
        Get PDF data for specific program.

        Normalizes ID to match PDF format:
        - HTML: "1D" -> PDF: "1.D"
        - HTML: "18" -> PDF: "18"
        - HTML: "20A" -> PDF: "20.A"
        """
        if not self._pdf_parser:
            return None

        # Normalize ID: add dots between number and letter
        normalized_id = self._normalize_program_id(program_id)

        # Try exact match first
        pdf_data = self._pdf_parser.get_program(normalized_id)
        if pdf_data:
            return pdf_data

        # Try without normalization
        return self._pdf_parser.get_program(program_id)

    def _normalize_program_id(self, program_id: str) -> str:
        """
        Normalize program ID to PDF format.

        Examples:
        - "1D" -> "1.D"
        - "18" -> "18"
        - "3A" -> "3.a" (series 3 uses lowercase!)
        - "20A" -> "20.A"
        - "9AA" -> "9.A.a"
        - "9AB13" -> "9.A.b.1"
        """
        import re

        # Handle special cases like 9AB13 -> 9.A.b.1.-3.
        if program_id == "9AB13":
            return "9.A.b.1"  # Try simplified version
        if program_id == "9AB4":
            return "9.A.b.4"

        # General pattern: split on case changes and numbers
        # "1D" -> ["1", "D"]
        # "20A" -> ["20", "A"]
        # "3A" -> ["3", "A"] -> "3.a" (special case for series 3)
        # "9AA" -> ["9", "A", "A"] -> "9.A.a"

        parts = re.findall(r'\d+|[A-Z][a-z]*', program_id)

        if len(parts) <= 1:
            return program_id

        # Special handling for series 3: first letter after number is lowercase
        # "3A" -> "3.a", "3B" -> "3.b", etc.
        if len(parts) == 2 and parts[0] == "3" and parts[1].isupper() and len(parts[1]) == 1:
            return f"3.{parts[1].lower()}"

        # Add dots between parts
        result = ".".join(parts)

        # Handle lowercase letters (sub-programs like 9.A.a)
        # If there are multiple uppercase letters, second becomes lowercase
        if len(parts) >= 3 and parts[2].isupper() and len(parts[2]) == 1:
            # 9AA -> 9.A.a
            result_parts = result.split('.')
            if len(result_parts) >= 3:
                result_parts[2] = result_parts[2].lower()
                result = '.'.join(result_parts)

        return result

    # ===== Content Building =====

    def _build_grant_content(
        self,
        program_id: str,
        url: str,
        html_data: dict,
        pdf_data: Optional[dict],
    ) -> GrantContent:
        """
        Combine HTML and PDF data into GrantContent object.

        Follows PRD schema requirements.
        """
        # Basic info
        name = pdf_data.get('name') if pdf_data else html_data.get('name', program_id)
        description = None
        summary = html_data.get('description')

        # PDF sections
        if pdf_data and 'sections' in pdf_data:
            sections = pdf_data['sections']

            # Build description from sections
            desc_parts = []
            for section_name in ['Účel', 'Předmět', 'Podmínky']:
                if section_name in sections:
                    desc_parts.append(f"{section_name}:\n{sections[section_name]}")

            description = '\n\n'.join(desc_parts) if desc_parts else summary

        # Funding amounts
        funding_amounts = pdf_data.get('funding_amounts') if pdf_data else None

        # Deadline
        deadline_info = pdf_data.get('deadline') if pdf_data else None

        # Eligibility
        eligibility = pdf_data.get('eligibility', []) if pdf_data else []

        # Documents
        documents = html_data.get('documents', [])

        # Add PDF Zásady as document
        if self._pdf_cache_path:
            documents.insert(0, Document(
                title=f"Zásady pro rok 2026 - Program {program_id}",
                url=f"https://szif.gov.cz/cs/CmDocument?rid=zasady_2026.pdf",
                doc_type='call_text',
                file_format='pdf',
                local_path=self._pdf_cache_path,
            ))

        # Build GrantContent
        content = GrantContent(
            source_url=url,
            scraper_name=self.get_scraper_name(),
            scraped_at=datetime.now(timezone.utc),
            description=description,
            summary=summary,
            funding_amounts=funding_amounts,
            documents=documents,
            eligible_recipients=eligibility,
            additional_metadata={
                'program_id': program_id,
                'program_name': name,
                'deadline': deadline_info,
                'news': html_data.get('news', []),
            },
        )

        return content
