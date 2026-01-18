"""
Base class for parser strategies.

Parsers implement the extraction phase - converting web pages
and documents into structured Grant objects.
"""

from abc import ABC, abstractmethod
from typing import Optional

import structlog

from grants_scraper.core.models import Grant, GrantTarget
from grants_scraper.core.http_client import HttpClient
from grants_scraper.navigators.base import SourceConfig

logger = structlog.get_logger(__name__)


class ParserStrategy(ABC):
    """
    Abstract base class for parser strategies.

    Parsers extract structured Grant data from discovered targets.
    Each strategy handles different content types:
    - HTML detail pages
    - PDF documents
    - Excel/CSV tables
    - Static information pages
    """

    def __init__(self, http_client: Optional[HttpClient] = None):
        """
        Initialize parser.

        Args:
            http_client: Shared HTTP client (creates own if not provided)
        """
        self.http_client = http_client
        self._owns_client = http_client is None
        self.logger = logger.bind(parser=self.__class__.__name__)

    async def __aenter__(self) -> "ParserStrategy":
        """Enter async context."""
        if self._owns_client:
            self.http_client = HttpClient()
            await self.http_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        if self._owns_client and self.http_client:
            await self.http_client.__aexit__(exc_type, exc_val, exc_tb)

    @abstractmethod
    async def extract(
        self,
        target: GrantTarget,
        source: SourceConfig,
    ) -> Optional[Grant]:
        """
        Extract grant data from target.

        Args:
            target: GrantTarget with URL and metadata
            source: Source configuration

        Returns:
            Grant object or None if extraction fails
        """
        pass

    async def extract_batch(
        self,
        targets: list[GrantTarget],
        source: SourceConfig,
    ) -> list[Grant]:
        """
        Extract grants from multiple targets.

        Args:
            targets: List of targets to process
            source: Source configuration

        Returns:
            List of successfully extracted grants
        """
        grants = []

        for i, target in enumerate(targets):
            self.logger.info(
                "extracting",
                index=i + 1,
                total=len(targets),
                url=target.url,
            )

            try:
                grant = await self.extract(target, source)
                if grant:
                    grants.append(grant)
            except Exception as e:
                self.logger.error(
                    "extraction_failed",
                    url=target.url,
                    error=str(e),
                )

        return grants

    def get_strategy_name(self) -> str:
        """Return human-readable strategy name."""
        return self.__class__.__name__
