"""Grantové scrapery pro EU fondy a české dotační programy."""

from .sources import (
    AbstractGrantSubScraper,
    Document,
    GrantContent,
    SubScraperRegistry,
)

__all__ = [
    "AbstractGrantSubScraper",
    "Document",
    "GrantContent",
    "SubScraperRegistry",
]
