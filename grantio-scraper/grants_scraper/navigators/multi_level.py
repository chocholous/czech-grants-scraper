"""
Multi-level navigator: L1 → L2 → ... → detail pages.

For hierarchical sites where grants are organized in
category → subcategory → detail structure.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from grants_scraper.core.models import GrantTarget
from grants_scraper.core.http_client import HttpClient

from .base import NavigatorStrategy, SourceConfig


@dataclass
class LevelConfig:
    """Configuration for one navigation level."""
    selector: str  # CSS selector for links at this level
    url_pattern: Optional[str] = None  # Regex to filter URLs
    is_leaf: bool = False  # True if this level contains grants


@dataclass
class MultiLevelSourceConfig(SourceConfig):
    """Extended config for multi-level navigation."""
    levels: list[LevelConfig] = field(default_factory=list)


class MultiLevelNavigator(NavigatorStrategy):
    """
    Multi-level navigator for hierarchical sites.

    Handles sites with category → subcategory → detail structure.
    Each level is configured with its own selector and URL pattern.

    Example:
        MZe SZIF: programs list → program detail → sub-programs
    """

    async def discover(
        self,
        source: SourceConfig,
        max_grants: Optional[int] = None,
    ) -> list[GrantTarget]:
        """
        Discover grants by traversing hierarchy.

        Args:
            source: Source configuration (or MultiLevelSourceConfig)
            max_grants: Optional limit

        Returns:
            List of GrantTarget objects
        """
        if not self.http_client:
            raise RuntimeError("Navigator not initialized. Use 'async with' context.")

        # Check if we have multi-level config
        if isinstance(source, MultiLevelSourceConfig) and source.levels:
            levels = source.levels
        else:
            # Fall back to single-level behavior
            levels = [
                LevelConfig(
                    selector=source.listing_selector,
                    url_pattern=source.detail_url_pattern,
                    is_leaf=True,
                )
            ]

        self.logger.info(
            "discovering_multi_level",
            source=source.source_id,
            levels=len(levels),
        )

        # Start discovery from root
        targets = await self._traverse_level(
            url=source.listing_url,
            source=source,
            levels=levels,
            level_index=0,
            max_grants=max_grants,
            seen_urls=set(),
        )

        self.logger.info(
            "discovery_complete",
            source=source.source_id,
            count=len(targets),
        )

        return targets

    async def _traverse_level(
        self,
        url: str,
        source: SourceConfig,
        levels: list[LevelConfig],
        level_index: int,
        max_grants: Optional[int],
        seen_urls: set[str],
    ) -> list[GrantTarget]:
        """
        Recursively traverse navigation levels.

        Args:
            url: Current page URL
            source: Source configuration
            levels: Level configurations
            level_index: Current level (0-indexed)
            max_grants: Optional limit
            seen_urls: Set of visited URLs

        Returns:
            List of GrantTarget objects
        """
        if level_index >= len(levels):
            return []

        if url in seen_urls:
            return []
        seen_urls.add(url)

        level = levels[level_index]
        targets: list[GrantTarget] = []

        self.logger.debug(
            "traversing_level",
            level=level_index + 1,
            url=url,
            is_leaf=level.is_leaf,
        )

        # Fetch page
        try:
            html = await self.http_client.get_text(url)
        except Exception as e:
            self.logger.warning("fetch_failed", url=url, error=str(e))
            return []

        soup = BeautifulSoup(html, "lxml")

        # Find links at this level
        links = soup.select(level.selector)

        for link in links:
            href = link.get("href")
            if not href:
                continue

            link_url = urljoin(source.base_url, href)

            # Validate URL pattern
            if level.url_pattern and not re.match(level.url_pattern, link_url):
                continue

            # Skip already seen
            if link_url in seen_urls:
                continue

            if level.is_leaf:
                # This is a grant link
                title = link.get_text(" ", strip=True)

                targets.append(
                    GrantTarget(
                        url=link_url,
                        title=title or None,
                        source_id=source.source_id,
                        metadata={
                            "source_name": source.source_name,
                            "parent_url": url,
                            "level": level_index + 1,
                        },
                    )
                )

                if max_grants and len(targets) >= max_grants:
                    return targets
            else:
                # Recurse to next level
                sub_targets = await self._traverse_level(
                    url=link_url,
                    source=source,
                    levels=levels,
                    level_index=level_index + 1,
                    max_grants=max_grants - len(targets) if max_grants else None,
                    seen_urls=seen_urls,
                )
                targets.extend(sub_targets)

                if max_grants and len(targets) >= max_grants:
                    return targets

        return targets
