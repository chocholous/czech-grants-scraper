"""
Core layer - stable foundation for the scraping system.

Components:
- models: Grant, Document, GrantTarget dataclasses
- http_client: Rate-limited, retrying HTTP client
- selectors: Unified CSS/XPath/Regex selection
- normalizer: Czech date, amount, text normalization
- deduplicator: Hash-based grant deduplication
"""

from .models import Grant, Document, GrantTarget, FundingAmount
from .normalizer import (
    parse_czech_date,
    parse_czech_amount,
    normalize_title,
    cleanup_html_text,
    extract_deadline,
    extract_all_dates,
    extract_funding_range,
    extract_funding_amounts,
    detect_currency,
)
from .deduplicator import Deduplicator, generate_content_hash

__all__ = [
    "Grant",
    "Document",
    "GrantTarget",
    "FundingAmount",
    "parse_czech_date",
    "parse_czech_amount",
    "normalize_title",
    "cleanup_html_text",
    "extract_deadline",
    "extract_all_dates",
    "extract_funding_range",
    "extract_funding_amounts",
    "detect_currency",
    "Deduplicator",
    "generate_content_hash",
]
