#!/usr/bin/env python3
"""
dotaceeu.cz Grant Scraper
Scrapes grant calls from dotaceeu.cz with AJAX pagination support
"""

# ============================================================================
# SECTION 1: Imports + Config Loading
# ============================================================================

import asyncio
import csv
import json
import logging
import os
import re
import sys
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict
from argparse import ArgumentParser

import yaml
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser
from dateutil import parser as date_parser

# Sub-scraper imports
from subscrapers import SubScraperRegistry, GrantContent, Document
from subscrapers.opst_cz import OPSTCzScraper
from subscrapers.mv_gov_cz import MVGovCzScraper
from subscrapers.nrb_cz import NRBCzScraper
from subscrapers.irop_mmr_cz import IROPGovCzScraper
from subscrapers.esfcr_cz import ESFCRCzScraper
from subscrapers.opzp_cz import OPZPCzScraper
from subscrapers.optak_gov_cz import OPTAKGovCzScraper
from subscrapers.sfzp_cz import SFZPCzScraper
from subscrapers.gacr_cz import GACRCzScraper
from subscrapers.tacr_cz import TACRCzScraper
from subscrapers.azvcr_cz import AZVCRCzScraper
from subscrapers.utils import download_document, convert_document_to_markdown


def load_config(config_path: str = "config.yml") -> Dict:
    """Load configuration from YAML with environment variable substitution"""
    with open(config_path, 'r') as f:
        config_text = f.read()

    # Substitute environment variables: ${VAR_NAME:-default}
    def replace_env(match):
        var_expr = match.group(1)
        if ':-' in var_expr:
            var_name, default = var_expr.split(':-', 1)
            return os.getenv(var_name, default)
        else:
            return os.getenv(var_expr, '')

    config_text = re.sub(r'\$\{([^}]+)\}', replace_env, config_text)
    return yaml.safe_load(config_text)


def setup_logging(config: Dict):
    """Configure logging"""
    log_level = config['logging']['level']
    log_file = config['logging']['file']

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


# ============================================================================
# SECTION 2: Data Models
# ============================================================================

@dataclass
class DotaceuGrant:
    """
    Represents a grant from dotaceeu.cz

    Handles two page types:
    - Type A (Czech OPs): Full metadata including call_number, eligible_applicants
    - Type B (EU direct): Simplified metadata, missing some fields
    """

    # Identifiers
    external_id: str              # Call number OR URL slug (if no call number)
    source_url: str               # Detail page URL

    # Core metadata
    call_number: Optional[str]            # Číslo výzvy (Type A only)
    title: str
    operational_programme: Optional[str]  # Operační program
    programming_period: Optional[str]     # Programové období
    priority_axis: Optional[str]          # Prioritní osa

    # Call details
    call_type: Optional[str]              # Průběžná/Kolová
    call_status: Optional[str]            # Otevřená/Uzavřená/Plánovaná
    eligible_applicants: Optional[str]    # Oprávnění žadatelé (Type A only - raw text)

    # Dates (CRITICAL)
    application_availability: Optional[datetime]  # Zpřístupnění žádosti o podporu
    application_start: Optional[datetime]         # Zahájení příjmu
    submission_deadline: Optional[datetime]       # Ukončení příjmu

    # Funding
    min_amount: Optional[float]           # Min support amount (from text parsing)
    max_amount: Optional[float]           # Max support amount (from text parsing)
    total_allocation: Optional[float]     # Total allocation if mentioned

    # Content
    description: Optional[str]
    attached_documents: List[dict]        # [{url, title, type}] - empty in v1
    application_link: Optional[str]       # Více informací na
    all_urls: List[str]                   # All URLs found in grant text

    # Computed fields
    is_ngo_eligible: bool                     # Derived from eligible_applicants
    page_type: str                            # "type_a" or "type_b"

    # Metadata
    scraped_at: datetime

    # Deep-scraped content (optional, populated by sub-scrapers)
    deep_content: Optional['GrantContent'] = None

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        result = {}
        for k, v in asdict(self).items():
            if k == 'deep_content':
                continue  # Handle separately
            if isinstance(v, datetime):
                result[k] = v.isoformat()
            else:
                result[k] = v

        # Include deep-scraped content if available
        if self.deep_content:
            result['deepContent'] = {
                'description': self.deep_content.description,
                'summary': self.deep_content.summary,
                'fundingAmounts': self.deep_content.funding_amounts,
                'documents': [d.to_dict() for d in self.deep_content.documents],
                'applicationUrl': self.deep_content.application_url,
                'contactEmail': self.deep_content.contact_email,
                'eligibleRecipients': self.deep_content.eligible_recipients,
            }
            # Include LLM-enhanced info if available
            if self.deep_content.enhanced_info:
                result['enhancedInfo'] = self.deep_content.enhanced_info.to_dict()

        return result

    def to_grantio_format(self) -> dict:
        """Convert to GrantSource-compatible JSON format"""
        return {
            "ExternalId": self.external_id,
            "Title": self.title,
            "WebSite": self.source_url,
            "Data": json.dumps(self.to_dict()),
        }


# ============================================================================
# SECTION 3: Utility Functions
# ============================================================================

def parse_czech_date(text: str) -> Optional[datetime]:
    """
    Parse Czech date format: '9. 1. 2026' or '30. 4. 2026'

    Returns datetime object or None if parsing fails
    """
    if not text:
        return None

    # Pattern: day. month. year
    pattern = r'(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})'
    match = re.search(pattern, text)

    if match:
        day, month, year = match.groups()
        try:
            return datetime(int(year), int(month), int(day))
        except ValueError as e:
            logging.warning(f"Invalid date: {text} - {e}")
            return None

    return None


def is_ngo_eligible(text: str, keywords: List[str]) -> bool:
    """
    Check if eligible_applicants text contains NGO keywords

    Keywords from validation: nadace, spolky, obecně prospěšné, etc.
    """
    if not text:
        return False

    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def generate_external_id(call_number: Optional[str], url: str) -> str:
    """
    Generate external_id: use call number if available, else URL slug

    For Type B pages without call numbers, we prefix with 'slug_'
    """
    if call_number:
        return call_number

    # Fallback: extract URL slug
    slug = url.rstrip('/').split('/')[-1]
    return f"slug_{slug}"


def is_grant_page_url(url: str) -> bool:
    """
    Check if URL looks like a grant detail page vs general info page.

    Used to filter URLs before deep scraping to avoid scraping
    non-grant pages like /kontakty/, /o-nas/, /dokumenty/, etc.
    """
    url_lower = url.lower()

    # Grant page URL patterns (whitelist)
    grant_patterns = [
        '/dotace/',           # SFZP, OPST, OPZP grant pages
        '/dotace-a-pujcky/', # SFZP grants and loans
        '/vyzva',            # Matches vyzva-, vyzvy-, Vyzvy- (ESFCR, IROP, etc.)
        '/vyhlaseni-',       # AZVCR call announcements
        '/program/',         # TACR programs
        '/souteze/',         # TACR competitions
        '/investicni-programy/', # NRB investment programs
        '/fondyeu/clanek/',  # MV EU funds articles (grant calls)
        '/aktualni-vyzvy/',  # GACR current calls
        '/nabidka-dotaci/',  # OPST grant offerings
    ]

    # Check if URL matches any grant pattern
    return any(pattern in url_lower for pattern in grant_patterns)


# ============================================================================
# SECTION 4: HTML Parser
# ============================================================================

def parse_grant_detail(html: str, url: str, config: Dict) -> Optional[DotaceuGrant]:
    """
    Parse grant detail page HTML into DotaceuGrant object

    Handles both Type A (full metadata) and Type B (simplified) pages
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Extract metadata fields
    info = extract_metadata_fields(soup)

    # Determine page type
    page_type = determine_page_type(info)

    # Extract title from h1
    title_elem = soup.find('h1')
    title = title_elem.get_text(strip=True) if title_elem else "Untitled"

    # Generate external ID
    call_number = info.get("Číslo výzvy")
    external_id = generate_external_id(call_number, url)

    # Check NGO eligibility
    eligible_text = info.get("Oprávnění žadatelé", "")
    ngo_eligible = is_ngo_eligible(eligible_text, config['filters']['ngo_keywords'])

    # Extract all URLs from page
    base_url = config['scraper']['base_url']
    all_urls = extract_all_urls(soup, base_url)

    # Extract funding amounts from text
    page_text = soup.get_text()
    min_amt, max_amt, total_alloc = extract_funding_amounts(page_text)

    grant = DotaceuGrant(
        external_id=external_id,
        source_url=url,
        call_number=call_number,
        title=title,
        operational_programme=info.get("Operační program"),
        programming_period=info.get("Programové období"),
        priority_axis=info.get("Prioritní osa"),
        call_type=info.get("Druh výzvy"),
        call_status=info.get("Stav výzvy"),
        eligible_applicants=eligible_text if eligible_text else None,
        application_availability=parse_czech_date(info.get("Zpřístupnění žádosti o podporu", "")),
        application_start=parse_czech_date(info.get("Zahájení příjmu žádostí", "")),
        submission_deadline=parse_czech_date(info.get("Ukončení příjmu žádostí", "")),
        min_amount=min_amt,
        max_amount=max_amt,
        total_allocation=total_alloc,
        description=None,  # Not available in current structure
        attached_documents=[],  # PDFs use JS PostBack - skip in v1
        application_link=info.get("Více informací na"),
        all_urls=all_urls,
        is_ngo_eligible=ngo_eligible,
        page_type=page_type,
        scraped_at=datetime.now(timezone.utc),
    )

    return grant


def extract_metadata_fields(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Extract metadata label-value pairs from page text

    dotaceeu.cz uses plain text labels with values in <strong> tags,
    NOT HTML tables as originally assumed
    """
    info = {}

    # Get all text content
    text = soup.get_text()

    # Define fields to extract (from validation)
    fields = [
        "Číslo výzvy",
        "Druh výzvy",
        "Operační program",
        "Prioritní osa",
        "Oprávnění žadatelé",
        "Zahájení příjmu žádostí",
        "Ukončení příjmu žádostí",
        "Stav výzvy",
        "Programové období",
        "Zpřístupnění žádosti o podporu",
        "Více informací na",
    ]

    # Extract each field using regex
    for field in fields:
        # Pattern: "Field name:\s*\n*\s*(value)"
        pattern = rf"{re.escape(field)}:\s*\n?\s*([^\n]+)"
        match = re.search(pattern, text, re.MULTILINE)

        if match:
            value = match.group(1).strip()
            # Remove any remaining markup artifacts
            value = re.sub(r'\*\*|<[^>]+>', '', value)
            info[field] = value

    return info


def determine_page_type(info: Dict[str, str]) -> str:
    """
    Determine if page is Type A (full metadata) or Type B (simplified)

    Type A: Czech OPs with call_number and eligible_applicants
    Type B: EU direct programs without these fields
    """
    has_call_number = "Číslo výzvy" in info
    has_eligible_applicants = "Oprávnění žadatelé" in info

    if has_call_number and has_eligible_applicants:
        return "type_a"
    else:
        return "type_b"


def extract_all_urls(soup: BeautifulSoup, base_url: str) -> List[str]:
    """
    Extract all absolute URLs from grant page

    Returns deduplicated list of URLs found in links
    """
    urls = []

    for link in soup.find_all('a', href=True):
        href = link['href']

        # Convert to absolute URL
        if href.startswith('http://') or href.startswith('https://'):
            urls.append(href)
        elif href.startswith('/'):
            urls.append(base_url + href)
        elif href.startswith('#'):
            # Skip anchor links
            continue
        elif href.startswith('javascript:'):
            # Skip javascript links
            continue
        else:
            # Relative URL
            urls.append(base_url + '/' + href)

    # Deduplicate while preserving order
    seen = set()
    deduplicated = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduplicated.append(url)

    return deduplicated


def extract_funding_amounts(text: str) -> tuple:
    """
    Extract min/max/total funding amounts from Czech text

    Handles formats like:
    - "500 mil. Kč" = 500 000 000
    - "10 000 000 Kč" = 10 000 000
    - "5,5 mil. Kč" = 5 500 000
    - "minimální částka: X"
    - "maximální částka: X"
    - "celková alokace: X"

    Returns: (min_amount, max_amount, total_allocation) in CZK
    """
    min_amt = None
    max_amt = None
    total_alloc = None

    if not text:
        return (min_amt, max_amt, total_alloc)

    def parse_amount(amount_str: str) -> Optional[float]:
        """Parse Czech currency format to float"""
        if not amount_str:
            return None

        # Remove spaces and common separators
        amount_str = amount_str.strip()

        # Handle millions (mil. or miliónů)
        if 'mil' in amount_str.lower():
            # Extract number before "mil"
            match = re.search(r'([\d\s,\.]+)\s*mil', amount_str, re.IGNORECASE)
            if match:
                num_str = match.group(1).replace(' ', '').replace(',', '.')
                try:
                    return float(num_str) * 1_000_000
                except ValueError:
                    return None

        # Handle billions (mld. or miliard)
        if 'mld' in amount_str.lower() or 'miliard' in amount_str.lower():
            match = re.search(r'([\d\s,\.]+)\s*mld', amount_str, re.IGNORECASE)
            if match:
                num_str = match.group(1).replace(' ', '').replace(',', '.')
                try:
                    return float(num_str) * 1_000_000_000
                except ValueError:
                    return None

        # Handle plain numbers with spaces (e.g., "10 000 000")
        match = re.search(r'([\d\s]+)\s*Kč', amount_str)
        if match:
            num_str = match.group(1).replace(' ', '')
            try:
                return float(num_str)
            except ValueError:
                return None

        return None

    # Search for minimum amount
    min_patterns = [
        r'minim[aá]ln[íi]\s+[čc][aá]stka[:\s]+([^\n]+?)(?:Kč|$)',
        r'minimum[:\s]+([^\n]+?)(?:Kč|$)',
        r'od\s+([^\n]+?)\s+Kč',
    ]
    for pattern in min_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match and not min_amt:
            min_amt = parse_amount(match.group(1))

    # Search for maximum amount
    max_patterns = [
        r'maxim[aá]ln[íi]\s+[čc][aá]stka[:\s]+([^\n]+?)(?:Kč|$)',
        r'maximum[:\s]+([^\n]+?)(?:Kč|$)',
        r'do\s+([^\n]+?)\s+Kč',
        r'až\s+([^\n]+?)\s+Kč',
    ]
    for pattern in max_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match and not max_amt:
            max_amt = parse_amount(match.group(1))

    # Search for total allocation
    alloc_patterns = [
        r'celkov[aá]\s+alokace[:\s]+([^\n]+?)(?:Kč|$)',
        r'alokace[:\s]+([^\n]+?)(?:Kč|$)',
        r'rozpočet[:\s]+([^\n]+?)(?:Kč|$)',
        r'celkov[yý]\s+rozpočet[:\s]+([^\n]+?)(?:Kč|$)',
    ]
    for pattern in alloc_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match and not total_alloc:
            total_alloc = parse_amount(match.group(1))

    return (min_amt, max_amt, total_alloc)


# ============================================================================
# SECTION 5: Crawler
# ============================================================================

class DotaceuCrawler:
    """Main crawler class for dotaceeu.cz"""

    def __init__(
        self,
        config: Dict,
        deep_scrape: bool = False,
        enable_llm: bool = False,
        llm_model: str = "anthropic/claude-haiku-4.5",
    ):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.grants = []
        self.processed_count = 0
        self.error_count = 0
        self.deep_scrape = deep_scrape
        self.enable_llm = enable_llm
        self.llm_model = llm_model

        # Initialize sub-scraper registry
        self.scraper_registry = None
        if deep_scrape:
            self.scraper_registry = SubScraperRegistry()
            # Register available sub-scrapers with LLM settings
            self.scraper_registry.register(OPSTCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.scraper_registry.register(MVGovCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.scraper_registry.register(NRBCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.scraper_registry.register(IROPGovCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.scraper_registry.register(ESFCRCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.scraper_registry.register(OPZPCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.scraper_registry.register(OPTAKGovCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.scraper_registry.register(SFZPCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.scraper_registry.register(GACRCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.scraper_registry.register(TACRCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.scraper_registry.register(AZVCRCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            self.logger.info(f"Deep scraping enabled. Registered {self.scraper_registry.count()} sub-scrapers: {self.scraper_registry.list_scrapers()}")
            if enable_llm:
                self.logger.info(f"LLM enrichment enabled with model: {llm_model}")

    async def run(self, max_grants: Optional[int] = None):
        """Main scraping orchestration"""
        self.logger.info("Starting dotaceeu.cz scraper")

        # Load state for resumability
        state_mgr = None
        if self.config['resume']['enabled']:
            state_mgr = StateManager(self.config)
            self.logger.info(f"Resume enabled. Already processed: {len(state_mgr.state.get('processed_ids', []))} grants")

        async with async_playwright() as p:
            self.playwright = p  # Store for browser recovery
            browser = await self.launch_browser(p)
            page = await browser.new_page()

            try:
                # Step 1: Navigate to listing page
                listing_url = self.config['scraper']['base_url'] + self.config['scraper']['listing_path']
                self.logger.info(f"Navigating to {listing_url}")

                # Navigate with browser recovery
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        await page.goto(listing_url, wait_until="domcontentloaded")
                        await asyncio.sleep(self.add_jitter(2000))

                        # Step 2: Load all pages via AJAX pagination
                        await self.load_all_pages(page)

                        # Step 3: Extract grant items from listing
                        grant_items = await self.extract_grant_items(page)
                        self.logger.info(f"Found {len(grant_items)} grants in listing")
                        break  # Success

                    except Exception as e:
                        error_msg = str(e)
                        if 'target' in error_msg.lower() and 'closed' in error_msg.lower():
                            if retry < max_retries - 1:
                                self.logger.warning(f"Browser crashed during pagination, attempting recovery (retry {retry + 1}/{max_retries})")

                                # Close old browser
                                try:
                                    await browser.close()
                                except:
                                    pass

                                # Create new browser and page
                                browser = await self.launch_browser(self.playwright)
                                page = await browser.new_page()
                                self.logger.info("Browser recovered successfully")
                                await asyncio.sleep(2)
                            else:
                                self.logger.error(f"Failed to load listing after {max_retries} browser recoveries")
                                raise
                        else:
                            raise

                # Apply max_grants limit to items to process
                if max_grants:
                    grant_items = grant_items[:max_grants]
                    self.logger.info(f"Limiting to first {max_grants} grants")

                # Step 4: Process each grant detail page
                skipped_count = 0
                for i, item in enumerate(grant_items, 1):
                    self.logger.info(f"Processing grant {i}/{len(grant_items)}: {item['title'][:50]}...")

                    # Attempt to process grant with browser recovery
                    max_browser_retries = 2
                    grant = None

                    for retry in range(max_browser_retries):
                        try:
                            grant = await self.scrape_grant_detail(page, item)

                            if grant:
                                # Check if already processed
                                if state_mgr and state_mgr.is_processed(grant.external_id):
                                    self.logger.info(f"Skipping {grant.external_id} (already processed)")
                                    skipped_count += 1
                                    break

                                # Deep scrape external sources if enabled
                                if self.deep_scrape and self.scraper_registry:
                                    await self.deep_scrape_grant(grant)

                                self.grants.append(grant)
                                self.processed_count += 1
                            else:
                                self.error_count += 1

                            break  # Success, exit retry loop

                        except Exception as e:
                            error_msg = str(e)

                            # Check if browser/page crashed
                            if 'target' in error_msg.lower() and 'closed' in error_msg.lower():
                                if retry < max_browser_retries - 1:
                                    self.logger.warning(f"Browser crashed, attempting recovery (retry {retry + 1}/{max_browser_retries})")

                                    # Close old browser if possible
                                    try:
                                        await browser.close()
                                    except:
                                        pass

                                    # Create new browser and page
                                    browser = await self.launch_browser(self.playwright)
                                    page = await browser.new_page()
                                    self.logger.info("Browser recovered successfully")

                                    # Wait before retry
                                    await asyncio.sleep(2)
                                else:
                                    self.logger.error(f"Failed to recover browser after {max_browser_retries} attempts")
                                    self.error_count += 1
                                    break
                            else:
                                # Non-browser error, log and continue
                                self.logger.error(f"Error processing grant: {e}")
                                self.error_count += 1
                                break

                    # Delay between items with random jitter
                    delay_ms = int(self.config['delays']['between_items'])
                    await asyncio.sleep(self.add_jitter(delay_ms))

                self.logger.info(f"Scraping complete. Processed: {self.processed_count}, Errors: {self.error_count}, Skipped: {skipped_count}")

            finally:
                await browser.close()

    async def launch_browser(self, playwright):
        """Launch Chromium browser with stealth configuration"""
        return await playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',  # Overcome limited resource problems
                '--disable-gpu',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )

    def add_jitter(self, delay_ms: int) -> float:
        """Add random jitter to delays (±20%)"""
        jitter = random.uniform(-0.2, 0.2)
        return (delay_ms * (1 + jitter)) / 1000

    async def load_all_pages(self, page: Page):
        """Click 'Load more' button until no more pages"""
        click_count = 0
        max_clicks = 50  # Safety limit

        button_selector = self.config['selectors']['load_more_button']
        item_selector = self.config['selectors']['ajax_item']

        while click_count < max_clicks:
            try:
                # Wait for load more button (use .first to handle multiple buttons)
                load_more = page.locator(button_selector).first

                # Check if button exists and is visible
                is_visible = await load_more.is_visible(timeout=2000)
                if not is_visible:
                    self.logger.info("No more pages to load (button not visible)")
                    break

                # Count items before click
                items_before = await page.locator(item_selector).count()

                # Click and wait for new content
                await load_more.click()
                click_count += 1

                # Wait for items count to increase
                await page.wait_for_function(
                    f"document.querySelectorAll('{item_selector}').length > {items_before}",
                    timeout=10000
                )

                self.logger.info(f"Loaded page {click_count}")

                # Delay after click with jitter
                delay_ms = int(self.config['delays']['load_more_click'])
                await asyncio.sleep(self.add_jitter(delay_ms))

            except TimeoutError:
                self.logger.warning(f"Timeout waiting for page {click_count+1}, assuming end of pagination")
                break
            except Exception as e:
                self.logger.error(f"Error loading more pages: {e}")
                break

        if click_count >= max_clicks:
            self.logger.warning(f"Reached max pagination clicks ({max_clicks})")

    async def extract_grant_items(self, page: Page) -> List[Dict]:
        """Extract all grant items from loaded listing"""
        items = page.locator(self.config['selectors']['ajax_item'])
        count = await items.count()

        grants = []
        for i in range(count):
            item = items.nth(i)

            # Extract title
            title_elem = item.locator("h3")
            title_text = await title_elem.text_content()

            # Extract link - the one that wraps the h3, not tag links
            # Use :has(h3) selector to get the right link
            link_elem = item.locator("a:has(h3)")
            href = await link_elem.get_attribute("href")

            if href and title_text:
                full_url = self.make_absolute_url(href)
                grants.append({
                    "title": title_text.strip(),
                    "url": full_url,
                })

        return grants

    async def scrape_grant_detail(self, page: Page, item: Dict) -> Optional[DotaceuGrant]:
        """Scrape individual grant detail page"""
        try:
            # Navigate with retry
            html = await self.retry_navigation(page, item['url'])

            # Parse HTML into DotaceuGrant
            grant = parse_grant_detail(html, item['url'], self.config)

            return grant

        except Exception as e:
            # Re-raise browser crash errors so they can be handled by recovery logic
            error_msg = str(e)
            if 'target' in error_msg.lower() and 'closed' in error_msg.lower():
                raise  # Re-raise to trigger browser recovery

            self.logger.error(f"Error scraping {item['url']}: {e}", exc_info=True)
            return None

    async def retry_navigation(self, page: Page, url: str, max_retries: int = 3) -> str:
        """Navigate with exponential backoff retry"""
        for attempt in range(1, max_retries + 1):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Delay after navigation with jitter
                delay_ms = int(self.config['delays']['page_navigation'])
                await asyncio.sleep(self.add_jitter(delay_ms))

                return await page.content()
            except Exception as e:
                if attempt == max_retries:
                    raise

                delay = 2 ** attempt  # 2s, 4s, 8s
                self.logger.warning(f"Retry {attempt}/{max_retries} for {url} after {delay}s: {e}")
                await asyncio.sleep(delay)

        raise Exception(f"Failed to navigate to {url} after {max_retries} attempts")

    async def deep_scrape_grant(self, grant: DotaceuGrant):
        """
        Deep scrape external sources for grant content.

        Follows external URLs, extracts full content, downloads documents,
        and converts them to markdown.
        """
        scraper = None
        target_url = None

        # Strategy 1: Construct URL from operational programme + call number
        # For OP ST grants, we can construct the opst.cz URL directly
        if grant.operational_programme and 'Spravedlivá transformace' in grant.operational_programme:
            # Extract grant number from call number (e.g., "10_25_102" → "102")
            if grant.call_number and '_' in grant.call_number:
                parts = grant.call_number.split('_')
                if len(parts) == 3:
                    grant_num = parts[2]
                    constructed_url = f"https://opst.cz/dotace/{grant_num}-vyzva/"

                    scraper = self.scraper_registry.get_scraper_for_url(constructed_url)
                    if scraper:
                        target_url = constructed_url
                        self.logger.info(f"Constructed OP ST URL: {target_url}")

        # Strategy 1b: IROP URL construction
        if not scraper and grant.operational_programme and 'Integrovaný regionální' in grant.operational_programme:
            # Extract call number from title (e.g., "118. výzva IROP" → "118")
            import re
            match = re.search(r'(\d+)\.\s*výzva\s+IROP', grant.title, re.IGNORECASE)
            if match:
                call_num = match.group(1)
                constructed_url = f"https://irop.gov.cz/Vyzvy-2021-2027/Vyzvy/{call_num}vyzvaIROP"

                scraper = self.scraper_registry.get_scraper_for_url(constructed_url)
                if scraper:
                    target_url = constructed_url
                    self.logger.info(f"Constructed IROP URL: {target_url}")

        # Strategy 1c: OPZP URL construction
        if not scraper and grant.operational_programme and 'Životní prostředí' in grant.operational_programme:
            # Extract call number from title (e.g., "MŽP_98. výzva" → "98")
            import re
            match = re.search(r'(\d+)\.\s*výzva', grant.title, re.IGNORECASE)
            if match:
                call_num = match.group(1)
                constructed_url = f"https://opzp.cz/dotace/{call_num}-vyzva/"

                scraper = self.scraper_registry.get_scraper_for_url(constructed_url)
                if scraper:
                    target_url = constructed_url
                    self.logger.info(f"Constructed OPZP URL: {target_url}")

        # Strategy 2: Check existing URLs for compatible scrapers
        # Only consider URLs that look like grant pages (not /kontakty/, /o-nas/, etc.)
        if not scraper and grant.all_urls:
            for url in grant.all_urls:
                if not is_grant_page_url(url):
                    continue
                scraper = self.scraper_registry.get_scraper_for_url(url)
                if scraper:
                    target_url = url
                    self.logger.debug(f"Found grant URL via Strategy 2: {url}")
                    break

        if not scraper:
            self.logger.debug(f"No sub-scraper found for {grant.external_id}")
            return

        self.logger.info(f"Deep scraping {grant.external_id} from {target_url} using {scraper.get_scraper_name()}")

        try:
            # Extract full content
            grant_metadata = {
                'title': grant.title,
                'call_number': grant.call_number,
                'external_id': grant.external_id,
            }

            content = await scraper.extract_content(target_url, grant_metadata)
            if not content:
                self.logger.warning(f"Failed to extract content from {target_url}")
                return

            # Create document directory
            doc_dir = Path(self.config['output']['path']).parent / 'documents' / grant.external_id
            doc_dir.mkdir(parents=True, exist_ok=True)

            # Download and convert documents
            converted_count = 0
            for doc in content.documents:
                try:
                    # Determine local filename
                    filename = f"{doc.doc_type}_{Path(doc.url).name}"
                    local_path = doc_dir / filename

                    # Download document
                    success = await scraper.download_document(doc.url, str(local_path))
                    if not success:
                        self.logger.warning(f"Failed to download {doc.url}")
                        continue

                    doc.local_path = str(local_path)

                    # Convert to markdown
                    if doc.file_format in ['pdf', 'xlsx', 'xlsm', 'docx']:
                        markdown = convert_document_to_markdown(str(local_path))

                        if markdown:
                            # Save markdown
                            markdown_filename = local_path.stem + '.md'
                            markdown_path = doc_dir / markdown_filename

                            with open(markdown_path, 'w', encoding='utf-8') as f:
                                f.write(markdown)

                            doc.markdown_path = str(markdown_path)
                            doc.markdown_content = markdown[:500] + '...' if len(markdown) > 500 else markdown  # Store preview
                            doc.conversion_method = doc.file_format
                            converted_count += 1

                            self.logger.debug(f"Converted {doc.title} to markdown ({len(markdown)} chars)")

                except Exception as e:
                    self.logger.error(f"Error processing document {doc.url}: {e}")
                    continue

            # Save GrantContent as JSON
            deep_dir = Path(self.config['output']['path']).parent / 'deep'
            deep_dir.mkdir(parents=True, exist_ok=True)
            content_file = deep_dir / f"{grant.external_id}.json"

            with open(content_file, 'w', encoding='utf-8') as f:
                json.dump(content.to_dict(), f, ensure_ascii=False, indent=2)

            # Store deep content on grant for dataset inclusion
            grant.deep_content = content

            self.logger.info(f"Deep scrape complete for {grant.external_id}: {len(content.documents)} documents, {converted_count} converted to markdown")
            if content.enhanced_info:
                self.logger.info(f"LLM enrichment: {len(content.enhanced_info.eligibility_criteria)} criteria, {len(content.enhanced_info.thematic_keywords)} keywords")

        except Exception as e:
            self.logger.error(f"Error during deep scrape of {grant.external_id}: {e}", exc_info=True)

    def make_absolute_url(self, href: str) -> str:
        """Convert relative URL to absolute"""
        base_url = self.config['scraper']['base_url']

        if href.startswith('http'):
            return href
        elif href.startswith('/'):
            return base_url + href
        else:
            return base_url + '/' + href


# ============================================================================
# SECTION 6: Storage + State Management
# ============================================================================

class StorageManager:
    """Handles JSON/CSV output and state management"""

    def __init__(self, config: Dict):
        self.config = config
        self.output_dir = Path(config['output']['path'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def save_json(self, grants: List[DotaceuGrant]) -> str:
        """Save grants as JSON (Grantio import format)"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"dotaceeu_grants_{timestamp}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(
                [g.to_grantio_format() for g in grants],
                f, ensure_ascii=False, indent=2
            )

        self.logger.info(f"Saved JSON: {filepath} ({len(grants)} grants)")
        return str(filepath)

    def save_csv(self, grants: List[DotaceuGrant]) -> str:
        """Save grants as CSV (human review)"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"dotaceeu_grants_{timestamp}.csv"
        filepath = self.output_dir / filename

        # Flatten nested structure
        rows = [
            {
                'Číslo výzvy': g.call_number or '',
                'Název': g.title,
                'Program': g.operational_programme or '',
                'Období': g.programming_period or '',
                'Typ': g.call_type or '',
                'Stav': g.call_status or '',
                'Uzávěrka': g.submission_deadline.strftime('%d.%m.%Y') if g.submission_deadline else '',
                'Zahájení': g.application_start.strftime('%d.%m.%Y') if g.application_start else '',
                'NGO způsobilé': 'ANO' if g.is_ngo_eligible else 'NE',
                'Typ stránky': g.page_type,
                'URL': g.source_url,
            }
            for g in grants
        ]

        if not rows:
            self.logger.warning("No grants to save to CSV")
            return str(filepath)

        # UTF-8 BOM for Excel compatibility
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        self.logger.info(f"Saved CSV: {filepath} ({len(grants)} grants)")
        return str(filepath)


class StateManager:
    """Track processed grants for resumability"""

    def __init__(self, config: Dict):
        self.state_file = Path(config['resume']['state_file'])
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self.load_state()
        self.logger = logging.getLogger(__name__)

    def load_state(self) -> Dict:
        """Load state from file"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "last_run": None,
            "processed_ids": [],
            "total_scraped": 0,
        }

    def is_processed(self, external_id: str) -> bool:
        """Check if grant was already processed"""
        return external_id in self.state.get("processed_ids", [])

    def save_state(self, processed_ids: List[str]):
        """Save state to file"""
        self.state["last_run"] = datetime.now(timezone.utc).isoformat()
        self.state["processed_ids"] = processed_ids
        self.state["total_scraped"] = len(processed_ids)

        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

        self.logger.info(f"Saved state: {len(processed_ids)} processed grants")


# ============================================================================
# SECTION 7: Main Execution
# ============================================================================

def main():
    """Main entry point"""
    parser = ArgumentParser(description='Scrape grant calls from dotaceeu.cz')
    parser.add_argument('--config', default='config.yml', help='Config file path')
    parser.add_argument('--output-format', choices=['json', 'csv', 'both'], help='Override output format')
    parser.add_argument('--ngo-only', action='store_true', help='Filter only NGO-eligible grants')
    parser.add_argument('--full-scrape', action='store_true', help='Ignore state and rescrape all')
    parser.add_argument('--max-grants', type=int, help='Limit number of grants to process (for testing)')
    parser.add_argument('--deep-scrape', action='store_true', help='Enable deep scraping: follow external URLs, download documents, convert to markdown')

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("dotaceeu.cz Grant Scraper")
    if args.deep_scrape:
        logger.info("MODE: Deep Scraping (with document extraction)")
    logger.info("=" * 80)

    # Override config from args
    if args.output_format:
        config['output']['format'] = args.output_format

    if args.full_scrape:
        config['resume']['enabled'] = False

    # Run crawler
    crawler = DotaceuCrawler(config, deep_scrape=args.deep_scrape)
    asyncio.run(crawler.run(max_grants=args.max_grants))

    # Filter NGO-only if requested
    grants = crawler.grants
    if args.ngo_only:
        grants = [g for g in grants if g.is_ngo_eligible]
        logger.info(f"Filtered to {len(grants)} NGO-eligible grants")

    # Save output
    storage = StorageManager(config)
    output_format = config['output']['format']

    if output_format in ['json', 'both']:
        storage.save_json(grants)

    if output_format in ['csv', 'both']:
        storage.save_csv(grants)

    # Save state
    if config['resume']['enabled']:
        state_mgr = StateManager(config)
        processed_ids = [g.external_id for g in crawler.grants]
        state_mgr.save_state(processed_ids)

    logger.info("=" * 80)
    logger.info(f"✓ Scraping complete!")
    logger.info(f"  Total scraped: {crawler.processed_count}")
    logger.info(f"  Errors: {crawler.error_count}")
    logger.info(f"  Output saved to: {config['output']['path']}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
