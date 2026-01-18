"""
Grants Scraper - Modular Czech grants scraping system.

Architecture:
- core/: Stable foundation (models, HTTP client, normalizers)
- navigators/: Discovery strategies (single-level, multi-level, document)
- parsers/: Extraction strategies (HTML, PDF, tables)
- plugins/: Optional extensions (PDF, Excel, LLM)
- config/: YAML-driven source definitions
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
