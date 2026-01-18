"""
Static navigator: single page = single grant.

For sources where one URL directly contains one grant's information
(no listing → detail navigation needed).
"""

from typing import Optional

from grants_scraper.core.models import GrantTarget

from .base import NavigatorStrategy, SourceConfig


class StaticNavigator(NavigatorStrategy):
    """
    Static navigator for single-grant pages.

    Used when a source URL directly contains grant information
    without any navigation needed. Common for:
    - Foundation grant programs
    - Municipal one-off grants
    - Single ongoing programs
    """

    async def discover(
        self,
        source: SourceConfig,
        max_grants: Optional[int] = None,
    ) -> list[GrantTarget]:
        """
        Return the source URL as a single target.

        For static sources, the listing URL is the grant page itself.

        Args:
            source: Source configuration
            max_grants: Ignored (always returns 1)

        Returns:
            List with single GrantTarget
        """
        self.logger.info(
            "static_discovery",
            source=source.source_id,
            url=source.listing_url,
        )

        return [
            GrantTarget(
                url=source.listing_url,
                title=source.source_name,
                source_id=source.source_id,
                metadata={
                    "source_name": source.source_name,
                    "type": "static",
                },
            )
        ]


class StaticListNavigator(NavigatorStrategy):
    """
    Static list navigator for predefined grant URLs.

    Used when grant URLs are known in advance (e.g., from config)
    rather than being discovered from a listing page.
    """

    def __init__(self, urls: list[str], **kwargs):
        """
        Initialize with predefined URLs.

        Args:
            urls: List of grant page URLs
        """
        super().__init__(**kwargs)
        self.urls = urls

    async def discover(
        self,
        source: SourceConfig,
        max_grants: Optional[int] = None,
    ) -> list[GrantTarget]:
        """
        Return predefined URLs as targets.

        Args:
            source: Source configuration
            max_grants: Optional limit

        Returns:
            List of GrantTarget objects
        """
        targets = []

        for i, url in enumerate(self.urls):
            if max_grants and i >= max_grants:
                break

            targets.append(
                GrantTarget(
                    url=url,
                    title=None,
                    source_id=source.source_id,
                    metadata={
                        "source_name": source.source_name,
                        "type": "static_list",
                        "index": i,
                    },
                )
            )

        self.logger.info(
            "static_list_discovery",
            source=source.source_id,
            count=len(targets),
        )

        return targets
