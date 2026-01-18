"""
Parser strategies for grant content extraction.

Parsers handle the extraction phase - converting HTML/PDF/Excel
pages into structured Grant objects.

Strategies:
- HtmlDetailParser: Parse HTML detail pages
- PdfParser: Extract from PDF documents
- TableParser: Extract from HTML/Excel tables
- StaticPageParser: Parse single-grant static pages
"""

from .base import ParserStrategy
from .html_detail import HtmlDetailParser

__all__ = [
    "ParserStrategy",
    "HtmlDetailParser",
]
