"""
Sub-scraper for azvcr.cz (Agency for Health Research of the Czech Republic).

Extracts calls, program descriptions, and related documents from azvcr.cz pages.
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
from .utils import download_document


class AZVCRCzScraper(AbstractGrantSubScraper):
    """Scraper for azvcr.cz grant call pages"""

    DOMAIN = "azvcr.cz"

    MAIN_SELECTORS = [
        "main",
        "#content",
        ".content",
        ".page-content",
        ".article",
        ".entry-content",
        ".main-content",
        ".content__body",
    ]

    SUMMARY_SELECTORS = [
        ".perex",
        ".lead",
        ".intro",
        ".summary",
    ]

    DOC_TYPE_PATTERNS = {
        "call_text": ["vyzva", "zadani", "call text"],
        "guidelines": ["pokyny", "metodika", "prirucka", "guidelines"],
        "template": ["sablona", "formular", "vzor", "template"],
        "budget": ["rozpocet", "budget", "kalkulace", "kalkulacka"],
        "annex": ["priloha", "annex", "attachment"],
        "faq": ["faq", "casto kladene", "otazky a odpovedi"],
    }

    def can_handle(self, url: str) -> bool:
        """Check if URL is from azvcr.cz domain"""
        parsed = urlparse(url)
        return self.DOMAIN in parsed.netloc

    async def extract_content(
        self, url: str, grant_metadata: dict, use_llm: Optional[bool] = None
    ) -> Optional[GrantContent]:
        """Extract grant content from azvcr.cz page"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.content, "html.parser")

            container = self._get_main_container(soup)
            description = self._extract_description(container)
            summary = self._extract_summary(container)
            documents = self._extract_documents(soup, url)
            funding_amounts = self._extract_funding_amounts(container.get_text(" ", strip=True))
            application_url = self._extract_application_url(soup)
            contact_email = self._extract_contact_email(soup)
            eligible_recipients = self._extract_eligible_recipients(soup)

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
                additional_metadata={
                    "page_title": self._extract_page_title(soup),
                },
            )

            self.logger.info(
                f"Extracted content from {url}: {len(documents)} documents, "
                f"{len(description or '')} chars description"
            )

            # LLM enrichment (optional)
            for elem in soup.select("nav, footer, script, style, header"):
                elem.decompose()
            page_text = soup.get_text(" ", strip=True)
            content = await self.enrich_with_llm(content, page_text, use_llm)

            return content
        except Exception as e:
            self.logger.error(f"Failed to extract content from {url}: {e}")
            return None

    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """Download document from azvcr.cz to local path"""
        return download_document(doc_url, save_path)

    def _get_main_container(self, soup: BeautifulSoup):
        for selector in self.MAIN_SELECTORS:
            container = soup.select_one(selector)
            if container:
                return container
        return soup.body or soup

    def _extract_page_title(self, soup: BeautifulSoup) -> Optional[str]:
        title_elem = soup.find("h1")
        if title_elem:
            return title_elem.get_text(strip=True)
        return soup.title.get_text(strip=True) if soup.title else None

    def _extract_summary(self, container: BeautifulSoup) -> Optional[str]:
        for selector in self.SUMMARY_SELECTORS:
            elem = container.select_one(selector)
            if elem:
                return elem.get_text(" ", strip=True)

        first_paragraph = container.find("p")
        if first_paragraph:
            return first_paragraph.get_text(" ", strip=True)
        return None

    def _extract_description(self, container: BeautifulSoup) -> Optional[str]:
        parts = []
        for elem in container.find_all(["h2", "h3", "h4", "p", "li"]):
            text = elem.get_text(" ", strip=True)
            if text:
                parts.append(text)
        return "\n\n".join(parts) if parts else None

    def _extract_documents(self, soup: BeautifulSoup, base_url: str) -> List[Document]:
        documents = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if not self._is_document_link(href):
                continue

            doc_url = urljoin(base_url, href)
            title = link.get_text(" ", strip=True) or Path(urlparse(doc_url).path).name
            file_format = self._get_file_format(doc_url)
            doc_type = self._classify_document_type(title)

            documents.append(
                Document(
                    title=title,
                    url=doc_url,
                    doc_type=doc_type,
                    file_format=file_format,
                )
            )
        return documents

    def _extract_funding_amounts(self, text: str) -> Optional[dict]:
        min_amt = self._extract_amount_by_keywords(
            text,
            ["minimalni castka", "minimum", "od"],
        )
        max_amt = self._extract_amount_by_keywords(
            text,
            ["maximalni castka", "maximum", "do", "az"],
        )
        total_amt = self._extract_amount_by_keywords(
            text,
            ["alokace", "rozpocet", "celkova alokace", "celkovy rozpocet"],
        )

        if not any([min_amt, max_amt, total_amt]):
            return None

        return {
            "min": min_amt,
            "max": max_amt,
            "total": total_amt,
            "currency": "CZK",
        }

    def _extract_application_url(self, soup: BeautifulSoup) -> Optional[str]:
        keywords = ["aplikace", "podat", "podani", "formular", "submission", "zadost"]
        for link in soup.find_all("a", href=True):
            text = link.get_text(" ", strip=True).lower()
            href = link["href"].lower()
            if any(keyword in text for keyword in keywords) or any(
                keyword in href for keyword in keywords
            ):
                return urljoin(f"https://{self.DOMAIN}", link["href"])
        return None

    def _extract_contact_email(self, soup: BeautifulSoup) -> Optional[str]:
        mailto = soup.select_one('a[href^="mailto:"]')
        if mailto:
            return mailto.get("href", "").replace("mailto:", "").strip()

        text = soup.get_text(" ", strip=True)
        match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        return match.group(0) if match else None

    def _extract_eligible_recipients(self, soup: BeautifulSoup) -> Optional[List[str]]:
        section_text = self._find_section_text(
            soup,
            [
                "opravneni zadatele",
                "opravneni prijemci",
                "kdo muze",
                "zpusobili zadatele",
                "prijemci podpory",
            ],
        )
        if not section_text:
            return None

        recipients = re.split(r"[,;]|\s+-\s+|\n", section_text)
        return [r.strip() for r in recipients if r.strip()]

    def _find_section_text(self, soup: BeautifulSoup, keywords: List[str]) -> Optional[str]:
        for heading in soup.find_all(["h2", "h3", "h4", "strong", "dt"]):
            heading_text = heading.get_text(" ", strip=True).lower()
            if any(keyword in heading_text for keyword in keywords):
                parts = []
                for sib in heading.find_next_siblings():
                    if sib.name in ["h2", "h3", "h4", "dt"]:
                        break
                    text = sib.get_text(" ", strip=True)
                    if text:
                        parts.append(text)
                if parts:
                    return " ".join(parts)
        return None

    def _classify_document_type(self, title: str) -> str:
        title_lower = title.lower()
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            if any(pattern in title_lower for pattern in patterns):
                return doc_type
        return "other"

    def _get_file_format(self, url: str) -> str:
        path = Path(urlparse(url).path)
        suffix = path.suffix.lower().lstrip(".")
        return suffix if suffix else "unknown"

    def _is_document_link(self, href: str) -> bool:
        href_lower = href.lower()
        return any(
            href_lower.endswith(ext)
            for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"]
        )

    def _parse_czech_amount(self, text: str) -> Optional[int]:
        if not text:
            return None

        cleaned = text.replace("Kc", "").replace("Kč", "").strip()
        cleaned = cleaned.replace("\u00a0", " ")

        if "mil" in cleaned.lower():
            num_str = re.sub(r"[^\d,\.]", "", cleaned)
            num_str = num_str.replace(",", ".")
            try:
                return int(float(num_str) * 1_000_000)
            except ValueError:
                return None

        num_str = re.sub(r"[^\d]", "", cleaned)
        try:
            return int(num_str)
        except ValueError:
            return None

    def _extract_amount_by_keywords(self, text: str, keywords: List[str]) -> Optional[int]:
        text_lower = text.lower()
        for keyword in keywords:
            pattern = rf"{keyword}[^\\d]*([\\d\\s\\.,]+\\s*(?:mil\\.?|mld\\.?|Kc|Kč)?)"
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                amount = self._parse_czech_amount(match.group(1))
                if amount:
                    return amount
        return None
