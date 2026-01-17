"""
Sub-scrapers for extracting full grant content from external sources.

Each operational program has its own scraper that extracts:
- Full grant descriptions
- Document URLs (PDFs, XLSX, DOCX)
- Funding amounts
- Application portals
- Contact information
"""

from .models import GrantContent, Document
from .registry import SubScraperRegistry
from .base import AbstractGrantSubScraper
from .mzcr_cz import MZCrCzScraper
from .justice_cz import JusticeCzScraper
from .mzv_cz import MZVCzScraper
from .vlada_cz import VladaCzScraper
from .mze_cz import MZeCzScraper
from .mdcr_cz import MDCrScraper
from .nsa_gov_cz import NSAGovCzScraper
from .mfcr_cz import MFCRCzScraper
from .eeagrants_cz import EEAGrantsCzScraper
from .mkcr_cz import MKCRCzScraper
from .army_cz import ArmyCzScraper
from .mpo_cz import MPOCzScraper
from .msmt_cz import MSMTCzScraper
from .opjak_cz import OPJAKCzScraper
from .tacr_cz import TACRCzScraper
from .gacr_cz import GACRCzScraper
from .mzd_gov_cz import MzdGovCz2026Scraper # <-- ADDED NEW SCRAPER

__all__ = [
    'GrantContent',
    'Document',
    'SubScraperRegistry',
    'AbstractGrantSubScraper',
    'MZCrCzScraper',
    'JusticeCzScraper',
    'MZVCzScraper',
    'VladaCzScraper',
    'MZeCzScraper',
    'MDCrScraper',
    'NSAGovCzScraper',
    'MFCRCzScraper',
    'EEAGrantsCzScraper',
    'MKCRCzScraper',
    'ArmyCzScraper',
    'MPOCzScraper',
    'MSMTCzScraper',
    'OPJAKCzScraper',
    'TACRCzScraper',
    'GACRCzScraper',
    'MzdGovCz2026Scraper', # <-- ADDED NEW SCRAPER
]