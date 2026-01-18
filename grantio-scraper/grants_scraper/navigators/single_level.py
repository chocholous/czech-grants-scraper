"""
Single-level navigator: listing → detail pages.

The most common pattern - finds grant links on a listing page
and returns them as targets for parsing.
"""

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from grants_scraper.core.models import GrantTarget
from grants_scraper.core.http_client import HttpClient

from .base import NavigatorStrategy, SourceConfig


class SingleLevelNavigator(NavigatorStrategy):
    """
    Single-level navigator for listing → detail pattern.

    Finds all grant links on listing page(s) and returns
    them as targets for the parser phase.

    Supports:
    - Simple CSS selector-based link extraction
    - URL pattern filtering
    - Pagination (click-based or URL-based)
    """

    async def discover(
        self,
        source: SourceConfig,
        max_grants: Optional[int] = None,
    ) -> list[GrantTarget]:
        """
        Discover grants from listing page.

        Args:
            source: Source configuration
            max_grants: Optional limit

        Returns:
            List of GrantTarget objects
        """
        if not self.http_client:
            raise RuntimeError("Navigator not initialized. Use 'async with' context.")

        self.logger.info(
            "discovering_grants",
            source=source.source_id,
            url=source.listing_url,
        )

        targets: list[GrantTarget] = []
        seen_urls: set[str] = set()

        # Handle pagination if configured
        if source.pagination_selector:
            targets = await self._discover_with_pagination(source, max_grants, seen_urls)
        else:
            targets = await self._discover_single_page(source, max_grants, seen_urls)

        self.logger.info(
            "discovery_complete",
            source=source.source_id,
            count=len(targets),
        )

        return targets

    async def _discover_single_page(
        self,
        source: SourceConfig,
        max_grants: Optional[int],
        seen_urls: set[str],
    ) -> list[GrantTarget]:
        """Extract targets from single listing page."""
        html = await self.http_client.get_text(source.listing_url)
        soup = BeautifulSoup(html, "lxml")

        return self._extract_targets(soup, source, max_grants, seen_urls)

    async def _discover_with_pagination(
        self,
        source: SourceConfig,
        max_grants: Optional[int],
        seen_urls: set[str],
    ) -> list[GrantTarget]:
        """Extract targets from paginated listing."""
        targets: list[GrantTarget] = []
        current_url = source.listing_url
        page_count = 0

        while page_count < source.max_pages:
            self.logger.debug("fetching_page", page=page_count + 1, url=current_url)

            html = await self.http_client.get_text(current_url)
            soup = BeautifulSoup(html, "lxml")

            # Extract from current page
            page_targets = self._extract_targets(soup, source, None, seen_urls)
            targets.extend(page_targets)

            # Check limit
            if max_grants and len(targets) >= max_grants:
                targets = targets[:max_grants]
                break

            # Find next page
            next_link = soup.select_one(source.pagination_selector)
            if not next_link or not next_link.get("href"):
                break

            next_url = urljoin(source.base_url, next_link["href"])
            if next_url == current_url:
                break

            current_url = next_url
            page_count += 1

        return targets

    def _extract_targets(
        self,
        soup: BeautifulSoup,
        source: SourceConfig,
        max_grants: Optional[int],
        seen_urls: set[str],
    ) -> list[GrantTarget]:
        """
        Extract grant targets from parsed page.

        Args:
            soup: Parsed HTML
            source: Source configuration
            max_grants: Optional limit
            seen_urls: Set of already seen URLs (for dedup)

        Returns:
            List of GrantTarget objects
        """
        targets: list[GrantTarget] = []

        # Find all links matching selector
        links = soup.select(source.listing_selector)

        for link in links:
            href = link.get("href")
            if not href:
                continue

            # Build absolute URL
            url = urljoin(source.base_url, href)

            # Skip if already seen
            if url in seen_urls:
                continue

            # Validate URL pattern if specified
            if source.detail_url_pattern:
                if not re.match(source.detail_url_pattern, url):
                    continue

            seen_urls.add(url)

            # Extract title from link text
            title = link.get_text(" ", strip=True)
            if not title:
                # Try to find title in parent or sibling elements
                parent = link.parent
                if parent:
                    h_tag = parent.find(["h1", "h2", "h3", "h4", "h5"])
                    if h_tag:
                        title = h_tag.get_text(" ", strip=True)

            targets.append(
                GrantTarget(
                    url=url,
                    title=title or None,
                    source_id=source.source_id,
                    metadata={
                        "source_name": source.source_name,
                        "listing_url": source.listing_url,
                    },
                )
            )

            # Check limit
            if max_grants and len(targets) >= max_grants:
                break

        return targets
