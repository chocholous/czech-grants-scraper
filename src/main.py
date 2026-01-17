#!/usr/bin/env python3
"""
Czech Grants Scraper - Apify Actor

Scrapes grant calls from dotaceeu.cz with AJAX pagination support
and optionally follows external links for deep scraping.
"""

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict
from urllib.parse import urlparse

from apify import Actor
from crawlee.crawlers import (
    PlaywrightCrawler,
    BeautifulSoupCrawler,
    PlaywrightCrawlingContext,
    BeautifulSoupCrawlingContext,
)
from bs4 import BeautifulSoup

# Import scrapers
import sys
from pathlib import Path

# Add scrapers to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.grants.sources.registry import SubScraperRegistry
from scrapers.grants.sources.opst_cz import OPSTCzScraper
from scrapers.grants.sources.mv_gov_cz import MVGovCzScraper
from scrapers.grants.sources.nrb_cz import NRBCzScraper
from scrapers.grants.sources.irop_mmr_cz import IROPGovCzScraper
from scrapers.grants.sources.esfcr_cz import ESFCRCzScraper
from scrapers.grants.sources.opzp_cz import OPZPCzScraper
from scrapers.grants.sources.optak_gov_cz import OPTAKGovCzScraper
from scrapers.grants.sources.sfzp_cz import SFZPCzScraper


class GrantParser:
    """Parse grant detail pages from dotaceeu.cz"""
    
    def __init__(self, ngo_keywords: List[str]):
        self.ngo_keywords = ngo_keywords
    
    def parse_czech_date(self, text: str) -> Optional[str]:
        """Parse Czech date format: '9. 1. 2026' to ISO format"""
        if not text:
            return None
        
        pattern = r'(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})'
        match = re.search(pattern, text)
        
        if match:
            day, month, year = match.groups()
            try:
                dt = datetime(int(year), int(month), int(day))
                return dt.isoformat()
            except ValueError as e:
                Actor.log.warning(f"Invalid date: {text} - {e}")
                return None
        
        return None
    
    def is_ngo_eligible(self, text: str) -> bool:
        """Check if eligible_applicants text contains NGO keywords"""
        if not text:
            return False
        
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in self.ngo_keywords)
    
    def extract_metadata_fields(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract metadata label-value pairs from page text"""
        info = {}
        text = soup.get_text()
        
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
        
        for field in fields:
            pattern = rf"{re.escape(field)}:\s*\n?\s*([^\n]+)"
            match = re.search(pattern, text, re.MULTILINE)
            
            if match:
                value = match.group(1).strip()
                value = re.sub(r'\*\*|<[^>]+>', '', value)
                info[field] = value
        
        return info
    
    def extract_funding_amounts(self, text: str) -> tuple:
        """Extract min/max/total funding amounts from Czech text"""
        min_amt = None
        max_amt = None
        total_alloc = None
        
        if not text:
            return (min_amt, max_amt, total_alloc)
        
        def parse_amount(amount_str: str) -> Optional[float]:
            """Parse Czech currency format to float"""
            if not amount_str:
                return None
            
            amount_str = amount_str.strip()
            
            # Handle millions
            if 'mil' in amount_str.lower():
                match = re.search(r'([\d\s,\.]+)\s*mil', amount_str, re.IGNORECASE)
                if match:
                    num_str = match.group(1).replace(' ', '').replace(',', '.')
                    try:
                        return float(num_str) * 1_000_000
                    except ValueError:
                        return None
            
            # Handle billions
            if 'mld' in amount_str.lower() or 'miliard' in amount_str.lower():
                match = re.search(r'([\d\s,\.]+)\s*mld', amount_str, re.IGNORECASE)
                if match:
                    num_str = match.group(1).replace(' ', '').replace(',', '.')
                    try:
                        return float(num_str) * 1_000_000_000
                    except ValueError:
                        return None
            
            # Handle plain numbers
            match = re.search(r'([\d\s]+)\s*Kč', amount_str)
            if match:
                num_str = match.group(1).replace(' ', '')
                try:
                    return float(num_str)
                except ValueError:
                    return None
            
            return None
        
        # Extract minimum amount
        min_patterns = [
            r'minim[aá]ln[íi]\s+[čc][aá]stka[:\s]+([^\n]+?)(?:Kč|$)',
            r'minimum[:\s]+([^\n]+?)(?:Kč|$)',
            r'od\s+([^\n]+?)\s+Kč',
        ]
        for pattern in min_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match and not min_amt:
                min_amt = parse_amount(match.group(1))
        
        # Extract maximum amount
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
        
        # Extract total allocation
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
    
    def parse_grant_detail(self, html: str, url: str) -> Optional[Dict]:
        """Parse grant detail page HTML into dictionary"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract metadata
        info = self.extract_metadata_fields(soup)
        
        # Extract title
        title_elem = soup.find('h1')
        title = title_elem.get_text(strip=True) if title_elem else "Untitled"
        
        # Generate external ID
        call_number = info.get("Číslo výzvy")
        if call_number:
            external_id = call_number
        else:
            slug = url.rstrip('/').split('/')[-1]
            external_id = f"slug_{slug}"
        
        # Check NGO eligibility
        eligible_text = info.get("Oprávnění žadatelé", "")
        ngo_eligible = self.is_ngo_eligible(eligible_text)
        
        # Extract funding amounts
        page_text = soup.get_text()
        min_amt, max_amt, total_alloc = self.extract_funding_amounts(page_text)
        
        # Determine page type
        has_call_number = "Číslo výzvy" in info
        has_eligible_applicants = "Oprávnění žadatelé" in info
        page_type = "type_a" if (has_call_number and has_eligible_applicants) else "type_b"
        
        # Extract all URLs
        all_urls = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('http'):
                all_urls.append(href)
        
        grant = {
            'external_id': external_id,
            'source_url': url,
            'call_number': call_number,
            'title': title,
            'operational_programme': info.get("Operační program"),
            'programming_period': info.get("Programové období"),
            'priority_axis': info.get("Prioritní osa"),
            'call_type': info.get("Druh výzvy"),
            'call_status': info.get("Stav výzvy"),
            'eligible_applicants': eligible_text if eligible_text else None,
            'application_availability': self.parse_czech_date(info.get("Zpřístupnění žádosti o podporu", "")),
            'application_start': self.parse_czech_date(info.get("Zahájení příjmu žádostí", "")),
            'submission_deadline': self.parse_czech_date(info.get("Ukončení příjmu žádostí", "")),
            'min_amount': min_amt,
            'max_amount': max_amt,
            'total_allocation': total_alloc,
            'application_link': info.get("Více informací na"),
            'all_urls': all_urls,
            'is_ngo_eligible': ngo_eligible,
            'page_type': page_type,
            'scraped_at': datetime.now(timezone.utc).isoformat(),
        }
        
        return grant


async def main():
    """Main Actor entry point"""
    async with Actor:
        # Get input
        actor_input = await Actor.get_input() or {}
        
        scrape_mode = actor_input.get('scrapeMode', 'basic')
        max_grants = actor_input.get('maxGrants', 0)
        ngo_only = actor_input.get('ngoOnly', False)
        sources = actor_input.get('sources', [])
        delays = actor_input.get('delays', {
            'pageNavigation': 3000,
            'loadMoreClick': 2000,
            'betweenItems': 500
        })
        ngo_keywords = actor_input.get('ngoKeywords', [
            "neziskov", "spolek", "nadace", "nadační fond",
            "obecně prospěšn", "NNO", "církevní"
        ])
        
        Actor.log.info(f"Starting Czech Grants Scraper")
        Actor.log.info(f"Mode: {scrape_mode}")
        Actor.log.info(f"Max grants: {max_grants if max_grants > 0 else 'unlimited'}")
        Actor.log.info(f"NGO only: {ngo_only}")
        
        # Push dummy data for testing
        Actor.log.info("Pushing dummy test data to dataset...")
        dummy_grant = {
            'external_id': 'TEST_001',
            'source_url': 'https://www.dotaceeu.cz/test',
            'call_number': 'TEST_001',
            'title': 'Test Grant - Dummy Data',
            'operational_programme': 'Test Operational Program',
            'programming_period': '2021-2027',
            'priority_axis': 'Test Priority',
            'call_type': 'Průběžná',
            'call_status': 'Otevřená',
            'eligible_applicants': 'Všichni žadatelé / All applicants',
            'application_availability': '2026-01-01T00:00:00',
            'application_start': '2026-01-15T00:00:00',
            'submission_deadline': '2026-12-31T23:59:59',
            'min_amount': 100000.0,
            'max_amount': 5000000.0,
            'total_allocation': 50000000.0,
            'application_link': 'https://example.com/apply',
            'all_urls': ['https://example.com/info', 'https://example.com/documents'],
            'is_ngo_eligible': True,
            'page_type': 'type_a',
            'scraped_at': datetime.now(timezone.utc).isoformat(),
        }
        await Actor.push_data(dummy_grant)
        Actor.log.info("✓ Dummy test data pushed successfully!")
        
        # Initialize parser
        parser = GrantParser(ngo_keywords)
        
        # Initialize sub-scraper registry for deep scraping
        scraper_registry = None
        if scrape_mode == 'deep':
            scraper_registry = SubScraperRegistry()
            scraper_registry.register(OPSTCzScraper())
            scraper_registry.register(MVGovCzScraper())
            scraper_registry.register(NRBCzScraper())
            scraper_registry.register(IROPGovCzScraper())
            scraper_registry.register(ESFCRCzScraper())
            scraper_registry.register(OPZPCzScraper())
            scraper_registry.register(OPTAKGovCzScraper())
            scraper_registry.register(SFZPCzScraper())
            Actor.log.info(f"Deep scraping enabled. Registered {scraper_registry.count()} sub-scrapers")
        
        # Track statistics
        stats = {
            'processed': 0,
            'errors': 0,
            'filtered': 0
        }
        
        # Storage for grant items from listing
        grant_items = []
        
        # Create Playwright crawler for dotaceeu.cz (AJAX pagination)
        listing_crawler = PlaywrightCrawler(
            max_requests_per_crawl=1,
            headless=True,
        )
        
        @listing_crawler.router.default_handler
        async def handle_listing(context: PlaywrightCrawlingContext):
            """Handle the listing page with AJAX pagination"""
            page = context.page
            
            Actor.log.info("Loading all pages via AJAX pagination...")
            
            # Click "Load more" button until no more pages
            click_count = 0
            max_clicks = 15  # Limit to stay under 60 second timeout
            
            button_selector = ".js-more-vyzvy"
            item_selector = ".js-ajax-item"
            
            Actor.log.info(f"Starting pagination (max {max_clicks} clicks to stay under timeout)...")
            
            pagination_start = time.time()
            
            while click_count < max_clicks:
                try:
                    load_more = page.locator(button_selector).first
                    is_visible = await load_more.is_visible(timeout=2000)
                    
                    if not is_visible:
                        Actor.log.info("No more pages to load")
                        break
                    
                    items_before = await page.locator(item_selector).count()
                    await load_more.click()
                    click_count += 1
                    
                    # Wait for items to increase
                    await page.wait_for_function(
                        f"document.querySelectorAll('{item_selector}').length > {items_before}",
                        timeout=10000
                    )
                    
                    if click_count % 5 == 0:  # Log every 5 pages instead of every page
                        Actor.log.info(f"Loaded {click_count} pages...")
                    await asyncio.sleep(delays['loadMoreClick'] / 1000)
                    
                except Exception as e:
                    Actor.log.warning(f"Pagination ended: {e}")
                    break
            
            pagination_time = time.time() - pagination_start
            Actor.log.info(f"Pagination complete. Clicked {click_count} times in {pagination_time:.1f}s.")
            
            # Extract all grant items
            items = page.locator(item_selector)
            count = await items.count()
            
            Actor.log.info(f"Found {count} grants in listing")
            
            for i in range(count):
                item = items.nth(i)
                
                # Extract title
                title_elem = item.locator("h3")
                title_text = await title_elem.text_content()
                
                # Extract link
                link_elem = item.locator("a:has(h3)")
                href = await link_elem.get_attribute("href")
                
                if href and title_text:
                    full_url = f"https://www.dotaceeu.cz{href}" if href.startswith('/') else href
                    grant_items.append({
                        "title": title_text.strip(),
                        "url": full_url,
                    })
        
        # Run listing crawler
        await listing_crawler.run(["https://www.dotaceeu.cz/cs/jak-ziskat-dotaci/vyzvy"])
        
        # Give Playwright time to clean up properly
        await asyncio.sleep(1)
        
        # Apply max grants limit
        if max_grants > 0 and len(grant_items) > max_grants:
            grant_items = grant_items[:max_grants]
            Actor.log.info(f"Limited to {max_grants} grants")
        
        # Create BeautifulSoup crawler for grant detail pages (faster, no JS needed)
        detail_crawler = BeautifulSoupCrawler(
            max_requests_per_crawl=len(grant_items) if grant_items else 1000,
        )
        
        @detail_crawler.router.default_handler
        async def handle_detail(context: BeautifulSoupCrawlingContext):
            """Handle individual grant detail page"""
            url = context.request.url
            html = context.http_response.read().decode('utf-8')
            
            try:
                # Parse grant
                grant = parser.parse_grant_detail(html, url)
                
                if grant:
                    # Filter NGO-only if requested
                    if ngo_only and not grant['is_ngo_eligible']:
                        stats['filtered'] += 1
                        return
                    
                    # Deep scrape if enabled
                    if scrape_mode == 'deep' and scraper_registry:
                        await deep_scrape_grant(grant, scraper_registry)
                    
                    # Push to dataset
                    await Actor.push_data(grant)
                    stats['processed'] += 1
                    
                    if stats['processed'] % 10 == 0:
                        Actor.log.info(f"Processed {stats['processed']} grants")
                else:
                    stats['errors'] += 1
                    
            except Exception as e:
                Actor.log.error(f"Error processing {url}: {e}")
                stats['errors'] += 1
            
            # Delay between items
            await asyncio.sleep(delays['betweenItems'] / 1000)
        
        # Run detail crawler
        detail_urls = [item['url'] for item in grant_items]
        if detail_urls:
            await detail_crawler.run(detail_urls)
        
        # Log final statistics
        Actor.log.info("=" * 60)
        Actor.log.info("Scraping complete!")
        Actor.log.info(f"Processed: {stats['processed']}")
        Actor.log.info(f"Errors: {stats['errors']}")
        Actor.log.info(f"Filtered: {stats['filtered']}")
        Actor.log.info("=" * 60)


async def deep_scrape_grant(grant: Dict, scraper_registry: SubScraperRegistry):
    """Deep scrape external sources for additional content"""
    scraper = None
    target_url = None
    
    # Try to find appropriate scraper for the grant
    operational_programme = grant.get('operational_programme', '')
    call_number = grant.get('call_number', '')
    
    # Strategy: Construct URL from operational programme
    if 'Spravedlivá transformace' in operational_programme and call_number and '_' in call_number:
        parts = call_number.split('_')
        if len(parts) == 3:
            grant_num = parts[2]
            target_url = f"https://opst.cz/dotace/{grant_num}-vyzva/"
            scraper = scraper_registry.get_scraper_for_url(target_url)
    
    # Check all URLs
    if not scraper:
        for url in grant.get('all_urls', []):
            scraper = scraper_registry.get_scraper_for_url(url)
            if scraper:
                target_url = url
                break
    
    if not scraper or not target_url:
        Actor.log.debug(f"No sub-scraper found for {grant['external_id']}")
        return
    
    try:
        Actor.log.info(f"Deep scraping {grant['external_id']} from {target_url}")
        
        grant_metadata = {
            'title': grant['title'],
            'call_number': grant.get('call_number'),
            'external_id': grant['external_id'],
        }
        
        content = await scraper.extract_content(target_url, grant_metadata)
        if content:
            # Store deep content in key-value store
            await Actor.set_value(f"deep_{grant['external_id']}", content.to_dict())
            Actor.log.info(f"Deep scrape complete: {len(content.documents)} documents")
    
    except Exception as e:
        Actor.log.error(f"Error during deep scrape: {e}")


if __name__ == "__main__":
    asyncio.run(main())
