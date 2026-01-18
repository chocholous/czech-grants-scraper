"""
Base class for navigator strategies.

Navigators implement the discovery phase of scraping - finding
all grant URLs from source listing pages.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import structlog

from grants_scraper.core.models import GrantTarget
from grants_scraper.core.http_client import HttpClient

logger = structlog.get_logger(__name__)


@dataclass
class SourceConfig:
    """Configuration for a grant source."""

    source_id: str
    source_name: str
    base_url: str

    # Discovery settings
    listing_url: str
    listing_selector: str = "a"  # CSS selector for grant links on listing

    # Optional settings
    detail_url_pattern: Optional[str] = None  # Regex to validate detail URLs
    pagination_selector: Optional[str] = None  # CSS selector for pagination
    max_pages: int = 50  # Safety limit for pagination

    # Rate limiting
    requests_per_second: float = 2.0

    # Extra metadata
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "SourceConfig":
        """Create from dictionary (e.g., from YAML)."""
        return cls(
            source_id=data["source_id"],
            source_name=data["source_name"],
            base_url=data["base_url"],
            listing_url=data["listing_url"],
            listing_selector=data.get("listing_selector", "a"),
            detail_url_pattern=data.get("detail_url_pattern"),
            pagination_selector=data.get("pagination_selector"),
            max_pages=data.get("max_pages", 50),
            requests_per_second=data.get("requests_per_second", 2.0),
            metadata=data.get("metadata", {}),
        )


class NavigatorStrategy(ABC):
    """
    Abstract base class for navigator strategies.

    Navigators discover grant URLs from source listing pages.
    Each strategy handles different page structures:
    - Single-level: listing → detail
    - Multi-level: category → subcategory → detail
    - Document: listing → PDF/Excel
    - Static: single page contains grant info
    """

    def __init__(self, http_client: Optional[HttpClient] = None):
        """
        Initialize navigator.

        Args:
            http_client: Shared HTTP client (creates own if not provided)
        """
        self.http_client = http_client
        self._owns_client = http_client is None
        self.logger = logger.bind(navigator=self.__class__.__name__)

    async def __aenter__(self) -> "NavigatorStrategy":
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
    async def discover(
        self,
        source: SourceConfig,
        max_grants: Optional[int] = None,
    ) -> list[GrantTarget]:
        """
        Discover grant targets from source.

        Args:
            source: Source configuration
            max_grants: Optional limit on number of grants

        Returns:
            List of GrantTarget objects with discovered URLs
        """
        pass

    def get_strategy_name(self) -> str:
        """Return human-readable strategy name."""
        return self.__class__.__name__
