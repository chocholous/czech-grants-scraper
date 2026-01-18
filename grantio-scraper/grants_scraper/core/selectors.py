"""
Unified selector interface for CSS, XPath, and Regex extraction.

Provides consistent API for extracting content from HTML using
different selection strategies.
"""

import re
from dataclasses import dataclass
from typing import Optional, Union
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

import structlog

logger = structlog.get_logger(__name__)


# Common selectors for finding main content
MAIN_SELECTORS = [
    "main",
    "#content",
    ".content",
    ".page-content",
    ".article",
    ".entry-content",
    ".main-content",
    ".content__body",
    "#main",
    ".post-content",
    "article",
]

# Selectors for summary/perex
SUMMARY_SELECTORS = [
    ".perex",
    ".lead",
    ".intro",
    ".summary",
    ".excerpt",
    ".teaser",
]

# Document type classification patterns (Czech + English)
DOC_TYPE_PATTERNS = {
    "call_text": ["vyzva", "výzva", "zadani", "zadání", "call text", "call_text"],
    "guidelines": ["pokyny", "metodika", "příručka", "prirucka", "guidelines", "manual"],
    "template": ["sablona", "šablona", "formular", "formulář", "vzor", "template"],
    "budget": ["rozpocet", "rozpočet", "kalkulace", "kalkulacka", "kalkulačka", "budget", "naklad"],
    "annex": ["priloha", "příloha", "annex", "attachment"],
    "faq": ["faq", "casto kladene", "často kladené", "otazky a odpovedi", "otázky a odpovědi"],
    "decision": ["rozhodnuti", "rozhodnutí", "decision"],
    "rules": ["pravidla", "podminky", "podmínky", "rules", "conditions"],
}

# File extensions for downloadable documents
DOCUMENT_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".odt", ".ods"]

# Keywords for finding eligible recipients
ELIGIBLE_RECIPIENTS_KEYWORDS = [
    "opravneni zadatele", "oprávnění žadatelé",
    "opravneni prijemci", "oprávnění příjemci",
    "kdo muze", "kdo může",
    "zpusobili zadatele", "způsobilí žadatelé",
    "prijemci podpory", "příjemci podpory",
    "cilova skupina", "cílová skupina",
]

# Keywords for finding application URL
APPLICATION_URL_KEYWORDS = [
    "aplikace", "podat", "podani", "podání",
    "formular", "formulář", "submission",
    "zadost", "žádost", "prihlaska", "přihláška",
]


@dataclass
class SelectorResult:
    """Result from selector extraction."""
    value: Optional[str] = None
    values: list[str] = None
    element: Optional[Tag] = None
    elements: list[Tag] = None
    found: bool = False

    def __post_init__(self):
        if self.values is None:
            self.values = []
        if self.elements is None:
            self.elements = []


class Selector:
    """
    Unified selector for HTML content extraction.

    Supports CSS selectors, XPath (via lxml), and regex patterns.
    """

    def __init__(self, soup: BeautifulSoup, base_url: str = ""):
        """
        Initialize selector with parsed HTML.

        Args:
            soup: BeautifulSoup parsed HTML
            base_url: Base URL for resolving relative links
        """
        self.soup = soup
        self.base_url = base_url

    def css(self, selector: str) -> SelectorResult:
        """
        Select elements using CSS selector.

        Args:
            selector: CSS selector string

        Returns:
            SelectorResult with matched elements
        """
        elements = self.soup.select(selector)
        if not elements:
            return SelectorResult(found=False)

        return SelectorResult(
            value=elements[0].get_text(" ", strip=True),
            values=[e.get_text(" ", strip=True) for e in elements],
            element=elements[0],
            elements=list(elements),
            found=True,
        )

    def css_one(self, selector: str) -> SelectorResult:
        """
        Select first element using CSS selector.

        Args:
            selector: CSS selector string

        Returns:
            SelectorResult with first match
        """
        element = self.soup.select_one(selector)
        if not element:
            return SelectorResult(found=False)

        return SelectorResult(
            value=element.get_text(" ", strip=True),
            element=element,
            found=True,
        )

    def regex(self, pattern: str, text: Optional[str] = None) -> SelectorResult:
        """
        Extract using regex pattern.

        Args:
            pattern: Regex pattern with groups
            text: Text to search (defaults to full page text)

        Returns:
            SelectorResult with matched groups
        """
        if text is None:
            text = self.soup.get_text(" ", strip=True)

        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if not match:
            return SelectorResult(found=False)

        groups = match.groups()
        return SelectorResult(
            value=groups[0] if groups else match.group(0),
            values=list(groups) if groups else [match.group(0)],
            found=True,
        )

    def regex_all(self, pattern: str, text: Optional[str] = None) -> SelectorResult:
        """
        Extract all matches using regex pattern.

        Args:
            pattern: Regex pattern
            text: Text to search

        Returns:
            SelectorResult with all matches
        """
        if text is None:
            text = self.soup.get_text(" ", strip=True)

        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if not matches:
            return SelectorResult(found=False)

        return SelectorResult(
            value=matches[0] if matches else None,
            values=matches,
            found=True,
        )

    def try_selectors(self, selectors: list[str]) -> SelectorResult:
        """
        Try multiple CSS selectors in order, return first match.

        Args:
            selectors: List of CSS selectors to try

        Returns:
            First successful SelectorResult
        """
        for selector in selectors:
            result = self.css_one(selector)
            if result.found:
                return result
        return SelectorResult(found=False)


def get_main_container(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Find the main content container in the page.

    Tries selectors from MAIN_SELECTORS in order.

    Args:
        soup: Parsed HTML

    Returns:
        Main container element or body/soup fallback
    """
    for selector in MAIN_SELECTORS:
        container = soup.select_one(selector)
        if container:
            return container
    return soup.body or soup


def cleanup_navigation(soup: BeautifulSoup) -> None:
    """
    Remove navigation, footer, scripts from soup.

    Modifies soup in place.
    """
    for elem in soup.select("nav, footer, script, style, header, aside, .sidebar, .menu, .navigation"):
        elem.decompose()


def extract_page_title(soup: BeautifulSoup) -> Optional[str]:
    """Extract page title from h1 or title tag."""
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    if soup.title:
        return soup.title.get_text(strip=True)
    return None


def extract_summary(container: BeautifulSoup) -> Optional[str]:
    """
    Extract summary/perex from container.

    Tries SUMMARY_SELECTORS first, falls back to first paragraph.
    """
    for selector in SUMMARY_SELECTORS:
        elem = container.select_one(selector)
        if elem:
            return elem.get_text(" ", strip=True)

    # Fallback: first substantial paragraph
    first_p = container.find("p")
    if first_p:
        text = first_p.get_text(" ", strip=True)
        if len(text) > 50:
            return text

    return None


def extract_description(container: BeautifulSoup) -> Optional[str]:
    """
    Extract full description from container.

    Collects text from headings, paragraphs, and list items.
    """
    parts = []
    for elem in container.find_all(["h2", "h3", "h4", "p", "li"]):
        text = elem.get_text(" ", strip=True)
        if text and len(text) > 10:
            parts.append(text)
    return "\n\n".join(parts) if parts else None


def classify_document_type(title: str) -> str:
    """
    Classify document type based on title.

    Args:
        title: Document title

    Returns:
        Document type string
    """
    title_lower = title.lower()
    for doc_type, patterns in DOC_TYPE_PATTERNS.items():
        if any(pattern in title_lower for pattern in patterns):
            return doc_type
    return "other"


def is_document_link(href: str) -> bool:
    """Check if URL points to a downloadable document."""
    href_lower = href.lower()
    return any(href_lower.endswith(ext) for ext in DOCUMENT_EXTENSIONS)


def get_file_format(url: str) -> str:
    """Extract file format from URL."""
    from pathlib import Path
    from urllib.parse import urlparse

    path = Path(urlparse(url).path)
    suffix = path.suffix.lower().lstrip(".")
    return suffix if suffix else "unknown"


def extract_documents(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """
    Extract all downloadable documents from page.

    Args:
        soup: Parsed HTML
        base_url: Base URL for resolving relative links

    Returns:
        List of document dicts with title, url, doc_type, file_format
    """
    documents = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not is_document_link(href):
            continue

        doc_url = urljoin(base_url, href)

        if doc_url in seen_urls:
            continue
        seen_urls.add(doc_url)

        title = link.get_text(" ", strip=True)
        if not title:
            from pathlib import Path
            from urllib.parse import urlparse
            title = Path(urlparse(doc_url).path).name

        documents.append({
            "title": title,
            "url": doc_url,
            "doc_type": classify_document_type(title),
            "file_format": get_file_format(doc_url),
        })

    return documents


def find_section_text(soup: BeautifulSoup, keywords: list[str]) -> Optional[str]:
    """
    Find text content of section identified by keywords in heading.

    Args:
        soup: Parsed HTML
        keywords: Keywords to search for in headings

    Returns:
        Section text or None
    """
    for heading in soup.find_all(["h2", "h3", "h4", "strong", "dt", "b"]):
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


def extract_contact_email(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract contact email from page.

    Tries mailto: links first, then regex search.
    """
    # Try mailto: links
    mailto = soup.select_one('a[href^="mailto:"]')
    if mailto:
        email = mailto.get("href", "").replace("mailto:", "").split("?")[0].strip()
        if email:
            return email

    # Fallback: regex
    text = soup.get_text(" ", strip=True)
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match.group(0) if match else None


def extract_application_url(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """
    Find URL for application submission.

    Searches for links containing APPLICATION_URL_KEYWORDS.
    """
    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True).lower()
        href = link["href"].lower()

        if any(kw in text or kw in href for kw in APPLICATION_URL_KEYWORDS):
            full_url = urljoin(base_url, link["href"])
            if not is_document_link(full_url):
                return full_url

    return None


def extract_eligible_recipients(soup: BeautifulSoup) -> Optional[list[str]]:
    """
    Extract list of eligible recipients.

    Searches for section with ELIGIBLE_RECIPIENTS_KEYWORDS.
    """
    section_text = find_section_text(soup, ELIGIBLE_RECIPIENTS_KEYWORDS)
    if not section_text:
        return None

    # Split by common delimiters
    recipients = re.split(r"[,;]|\s+-\s+|\n|•|·", section_text)
    result = [r.strip() for r in recipients if r.strip() and len(r.strip()) > 3]
    return result if result else None
