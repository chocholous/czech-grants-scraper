"""
Configuration for MZe National Grants Scraper
"""

# Base URLs
SZIF_BASE_URL = "https://szif.gov.cz"
SZIF_NARODNI_DOTACE_URL = f"{SZIF_BASE_URL}/cs/narodni-dotace"
SZIF_PROGRAMY_LIST_URL = f"{SZIF_BASE_URL}/cs/nd-dotacni-programy"

# User agent for requests
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Output paths
OUTPUT_DIR = "output"
DATA_DIR = "data"

# PDF parsing
PDF_TEMP_DIR = "data/temp"

# Years to scrape (configurable)
CURRENT_YEAR = 2026
YEARS_TO_SCRAPE = [2025, 2026]
