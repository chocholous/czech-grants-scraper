"""
HTML detail page parser.

Extracts structured grant data from HTML detail pages using
CSS selectors and regex patterns.
"""

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from grants_scraper.core.models import (
    Grant,
    GrantTarget,
    GrantStatus,
    GrantType,
    FundingAmount,
    Document,
)
from grants_scraper.core.normalizer import (
    parse_czech_date,
    parse_czech_amount,
    normalize_title,
    cleanup_html_text,
    extract_funding_amounts,
)
from grants_scraper.core.selectors import (
    Selector,
    get_main_container,
    cleanup_navigation,
    extract_page_title,
    extract_summary,
    extract_description,
    extract_documents,
    extract_contact_email,
    extract_application_url,
    extract_eligible_recipients,
)
from grants_scraper.core.deduplicator import generate_content_hash
from grants_scraper.navigators.base import SourceConfig

from .base import ParserStrategy


class HtmlDetailParser(ParserStrategy):
    """
    Parser for HTML grant detail pages.

    Extracts:
    - Title, description, summary
    - Funding amounts (min, max, total)
    - Deadlines
    - Eligibility criteria
    - Contact information
    - Downloadable documents
    """

    async def extract(
        self,
        target: GrantTarget,
        source: SourceConfig,
    ) -> Optional[Grant]:
        """
        Extract grant from HTML detail page.

        Args:
            target: GrantTarget with URL
            source: Source configuration

        Returns:
            Grant object or None
        """
        if not self.http_client:
            raise RuntimeError("Parser not initialized. Use 'async with' context.")

        self.logger.info("parsing_html", url=target.url)

        try:
            html = await self.http_client.get_text(target.url)
        except Exception as e:
            self.logger.error("fetch_failed", url=target.url, error=str(e))
            return None

        return self._parse_html(html, target, source)

    def _parse_html(
        self,
        html: str,
        target: GrantTarget,
        source: SourceConfig,
    ) -> Optional[Grant]:
        """
        Parse HTML content into Grant.

        Args:
            html: Raw HTML content
            target: Grant target info
            source: Source configuration

        Returns:
            Grant object or None
        """
        soup = BeautifulSoup(html, "lxml")

        # Clean up navigation elements
        cleanup_navigation(soup)

        # Get main content container
        container = get_main_container(soup)

        # Create selector for advanced extraction
        selector = Selector(soup, source.base_url)

        # Extract title
        title = target.title or extract_page_title(soup)
        if not title:
            self.logger.warning("no_title", url=target.url)
            return None

        title = normalize_title(title)

        # Extract content
        summary = extract_summary(container)
        description = extract_description(container)

        # Extract deadline
        deadline = self._extract_deadline(soup, selector)

        # Extract funding amounts
        page_text = soup.get_text(" ", strip=True)
        funding_dict = extract_funding_amounts(page_text)
        funding_amount = None
        if any(v for k, v in funding_dict.items() if k != "currency"):
            funding_amount = FundingAmount(
                min=funding_dict.get("min"),
                max=funding_dict.get("max"),
                total=funding_dict.get("total"),
                currency=funding_dict.get("currency", "CZK"),
            )

        # Extract contact
        contact_email = extract_contact_email(soup)

        # Extract application URL
        application_url = extract_application_url(soup, source.base_url)

        # Extract eligibility
        eligible_recipients = extract_eligible_recipients(soup)

        # Extract documents
        doc_dicts = extract_documents(soup, source.base_url)
        documents = [
            Document(
                title=d["title"],
                url=d["url"],
                doc_type=d["doc_type"],
                file_format=d["file_format"],
            )
            for d in doc_dicts
        ]

        # Determine status
        status = GrantStatus.OK
        status_notes = ""
        if not deadline:
            status = GrantStatus.PARTIAL
            status_notes = "Missing deadline"

        # Generate content hash
        content_hash = generate_content_hash(
            source_id=source.source_id,
            url=target.url,
            title=title,
            deadline=deadline.isoformat() if deadline else None,
        )

        # Build Grant
        grant = Grant(
            source_id=source.source_id,
            source_name=source.source_name,
            source_url=source.base_url,
            grant_url=target.url,
            title=title,
            description=cleanup_html_text(description) if description else None,
            summary=cleanup_html_text(summary) if summary else None,
            funding_amount=funding_amount,
            deadline=deadline,
            grant_type=GrantType.CALL,
            status=status,
            status_notes=status_notes,
            eligibility=eligible_recipients or [],
            contact_email=[contact_email] if contact_email else [],
            documents=documents,
            application_url=application_url,
            content_hash=content_hash,
            extracted_at=datetime.now(timezone.utc),
            additional_metadata=target.metadata,
        )

        self.logger.info(
            "parsed_grant",
            title=title[:50],
            deadline=deadline.isoformat() if deadline else None,
            documents=len(documents),
        )

        return grant

    def _extract_deadline(
        self,
        soup: BeautifulSoup,
        selector: Selector,
    ) -> Optional[datetime]:
        """
        Extract deadline from page.

        Tries multiple patterns for Czech deadline formats.
        """
        # Common deadline patterns
        deadline_patterns = [
            r"uzávěrka[:\s]+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})",
            r"ukončení příjmu[:\s]+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})",
            r"deadline[:\s]+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})",
            r"termín[:\s]+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})",
            r"do\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})",
            r"nejpozději\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})",
        ]

        page_text = soup.get_text(" ", strip=True)

        for pattern in deadline_patterns:
            result = selector.regex(pattern, page_text)
            if result.found and result.value:
                deadline = parse_czech_date(result.value)
                if deadline:
                    return deadline

        # Try to find any date in deadline-related context
        deadline_keywords = ["uzávěrka", "deadline", "ukončení", "termín"]
        for kw in deadline_keywords:
            # Find keyword position
            pos = page_text.lower().find(kw)
            if pos >= 0:
                # Look for date in following 100 chars
                context = page_text[pos:pos + 100]
                deadline = parse_czech_date(context)
                if deadline:
                    return deadline

        return None
