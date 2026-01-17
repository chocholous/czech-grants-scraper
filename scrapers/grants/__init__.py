"""Grantové scrapery pro EU fondy a české dotační programy."""

from .sources import (
    AbstractGrantSubScraper,
    GrantContent,
    SubScraperRegistry,
)

__all__ = [
    "AbstractGrantSubScraper",
    "GrantContent",
    "SubScraperRegistry",
]
