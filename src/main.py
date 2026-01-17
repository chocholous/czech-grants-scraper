"""
Main entry point for MZ Grants Scraper Actor.

Orchestrates execution modes:
- search: Query existing dataset
- refresh: Force scrape all sources
- auto: Scrape if stale, then search
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Dict, List, Optional

from apify import Actor

# Add scrapers directory to path for imports
SCRAPERS_DIR = Path(__file__).parent.parent / "scrapers" / "grants"
sys.path.insert(0, str(SCRAPERS_DIR))

# Import MZ scraper components
from src.scraper import MZScraper
from src.mapper import map_to_prd_schema, validate_prd_record
from src.utils import is_date_in_past


# Source metadata
SOURCE_ID = "mz-grants"
SOURCE_NAME = "Ministerstvo zdravotnictví"


class ReadinessHandler(BaseHTTPRequestHandler):
    """HTTP handler for Apify readiness probes"""

    def do_GET(self):
        if "x-apify-container-server-readiness-probe" in self.headers:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Readiness probe OK")
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Actor is ready")

    def log_message(self, *_args, **_kwargs):
        # Suppress HTTP logs
        return


def start_readiness_server() -> Optional[ThreadingHTTPServer]:
    """Start HTTP server for readiness probes"""
    port_env = os.getenv("APIFY_CONTAINER_PORT") or os.getenv("PORT") or "3000"
    try:
        port = int(port_env)
    except ValueError:
        port = 3000

    # Try to bind to port, fallback to next port if occupied
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            server = ThreadingHTTPServer(("0.0.0.0", port), ReadinessHandler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            Actor.log.info(f"Readiness server listening on port {port}")
            return server
        except OSError as e:
            if e.errno == 48:  # Address already in use
                Actor.log.debug(f"Port {port} in use, trying {port + 1}")
                port += 1
            else:
                raise

    Actor.log.warning(f"Could not find free port after {max_attempts} attempts")
    return None


async def run_actor():
    """Main actor entry point"""
    readiness_server = None

    async with Actor:
        # Detect standby mode and start web UI
        if os.getenv('APIFY_META_ORIGIN') == 'STANDBY':
            Actor.log.info("Standby mode detected, starting web UI")
            from .web_ui import start_web_server

            # Start web UI and wait indefinitely
            await start_web_server()
            return  # Never return to normal logic

        # Start readiness server for normal mode
        readiness_server = start_readiness_server()

        # Get actor input
        actor_input = await Actor.get_input() or {}
        Actor.log.info(f"Actor input: {actor_input}")

        # Validate and extract input parameters
        mode = actor_input.get('mode', 'auto')
        query = actor_input.get('query')
        only_active = actor_input.get('onlyActive', True)
        stale_after_days = actor_input.get('staleAfterDays', 7)
        limit = actor_input.get('limit', 100)

        # Validate mode
        if mode not in ['search', 'refresh', 'auto']:
            Actor.log.error(f"Invalid mode: {mode}. Must be 'search', 'refresh', or 'auto'")
            if readiness_server:
                readiness_server.shutdown()
            await Actor.fail(status_message=f"Invalid mode: {mode}")
            return

        Actor.log.info(f"Mode: {mode}, onlyActive: {only_active}, staleAfterDays: {stale_after_days}")

        # Execute based on mode
        results = []
        try:
            if mode == 'search':
                results = await search_mode(actor_input)
                await store_run_summary(mode, scraped=0, results=len(results), errors=0)

            elif mode == 'refresh':
                scraped, errors = await refresh_mode()
                results = await search_mode(actor_input)
                await store_run_summary(mode, scraped=scraped, results=len(results), errors=errors)

            elif mode == 'auto':
                # Check staleness
                last_fetched = await get_last_fetched(SOURCE_ID)
                is_stale = check_staleness(last_fetched, stale_after_days)

                Actor.log.info(f"Last fetched: {last_fetched}, is_stale: {is_stale}")

                if is_stale:
                    Actor.log.info("Data is stale, triggering refresh")
                    scraped, errors = await refresh_mode()
                else:
                    Actor.log.info("Data is fresh, skipping scrape")
                    scraped, errors = 0, 0

                # Always return search results
                results = await search_mode(actor_input)
                await store_run_summary(mode, scraped=scraped, results=len(results), errors=errors)

            Actor.log.info("Actor completed successfully")

        except Exception as e:
            Actor.log.exception(f"Actor failed with error: {e}")
            if readiness_server:
                readiness_server.shutdown()
            await Actor.fail(status_message=str(e))
            return

        # Shutdown readiness server
        if readiness_server:
            readiness_server.shutdown()


async def refresh_mode() -> tuple[int, int]:
    """
    Refresh mode: Force scrape all sources.

    Returns:
        Tuple of (scraped_count, error_count)
    """
    Actor.log.info("Starting refresh mode")

    scraper = MZScraper()

    # Get all program URLs
    program_urls = scraper.list_program_urls()

    if not program_urls:
        Actor.log.warning("No program URLs found")
        return 0, 0

    Actor.log.info(f"Found {len(program_urls)} programs to scrape")

    scraped_count = 0
    error_count = 0

    # Open dataset
    dataset = await Actor.open_dataset(name="czech-grants")

    # Scrape each program
    for url in program_urls:
        try:
            Actor.log.info(f"Scraping: {url}")

            # Extract content
            content = await scraper.extract_content(url, {})

            if not content:
                Actor.log.warning(f"Failed to extract content from {url}")
                error_count += 1

                # Push error record
                await push_error_record(dataset, url, "Failed to extract content")
                continue

            # Map to PRD schema
            prd_record = map_to_prd_schema(
                content=content,
                source_id=SOURCE_ID,
                source_name=SOURCE_NAME,
                grant_url=url,
            )

            # Validate
            is_valid, missing = validate_prd_record(prd_record)
            if not is_valid:
                Actor.log.warning(f"Record has missing fields: {missing}")
                prd_record['status'] = 'partial'
                prd_record['statusNotes'] = f"Missing fields: {', '.join(missing)}"

            # Push to dataset
            await dataset.push_data(prd_record)
            scraped_count += 1

            Actor.log.info(f"Successfully scraped: {prd_record.get('title', 'unknown')}")

        except Exception as e:
            Actor.log.error(f"Error scraping {url}: {e}")
            error_count += 1

            # Push error record
            await push_error_record(dataset, url, str(e))

    # Update lastFetchedAt timestamp
    await set_last_fetched(SOURCE_ID, datetime.now(timezone.utc))

    Actor.log.info(f"Refresh completed: {scraped_count} scraped, {error_count} errors")
    return scraped_count, error_count


async def search_mode(actor_input: Dict) -> List[Dict]:
    """
    Search mode: Query existing dataset.

    Args:
        actor_input: Actor input parameters

    Returns:
        List of matching grant records
    """
    Actor.log.info("Starting search mode")

    # Open dataset and get all records
    dataset = await Actor.open_dataset(name="czech-grants")
    limit = int(actor_input.get('limit', 100))
    data = await dataset.get_data(limit=limit)
    all_records = data.items or []

    Actor.log.info(f"Loaded {len(all_records)} records from dataset")

    # Filter by source
    records = [r for r in all_records if r.get('sourceId') == SOURCE_ID]
    Actor.log.info(f"Filtered to {len(records)} MZ records")

    # Apply filters
    query = actor_input.get('query')
    only_active = actor_input.get('onlyActive', True)

    # Filter by query (simple keyword search in title and description)
    if query:
        query_lower = query.lower()
        records = [
            r for r in records
            if query_lower in r.get('title', '').lower()
            or query_lower in r.get('description', '').lower()
        ]
        Actor.log.info(f"Query filter: {len(records)} records match '{query}'")

    # Filter by active status (deadline in future)
    if only_active:
        records = [
            r for r in records
            if r.get('deadline') and not is_date_in_past(r.get('deadline'))
        ]
        Actor.log.info(f"Active filter: {len(records)} active grants")

    # Apply limit
    if limit and limit > 0:
        records = records[:limit]

    Actor.log.info(f"Returning {len(records)} results")
    return records


def check_staleness(last_fetched: Optional[datetime], stale_after_days: int) -> bool:
    """Check if data is stale based on last fetch time"""
    if not last_fetched:
        return True

    days_since_fetch = (datetime.now(timezone.utc) - last_fetched).days
    return days_since_fetch > stale_after_days


async def get_last_fetched(source_id: str) -> Optional[datetime]:
    """Get lastFetchedAt timestamp for a source from KV Store"""
    try:
        key = f"lastFetchedAt-{source_id}"
        value = await Actor.get_value(key)

        if value:
            from dateutil import parser as date_parser
            return date_parser.parse(value)

        return None

    except Exception as e:
        Actor.log.error(f"Failed to get lastFetchedAt for {source_id}: {e}")
        return None


async def set_last_fetched(source_id: str, timestamp: datetime) -> None:
    """Update lastFetchedAt timestamp for a source in KV Store"""
    try:
        key = f"lastFetchedAt-{source_id}"
        value = timestamp.isoformat()
        await Actor.set_value(key, value)
        Actor.log.debug(f"Updated lastFetchedAt for {source_id}: {value}")

    except Exception as e:
        Actor.log.error(f"Failed to set lastFetchedAt for {source_id}: {e}")
        raise


async def push_error_record(dataset, url: str, error_message: str) -> None:
    """Push error record to dataset"""
    error_record = {
        'recordType': 'grant',
        'sourceId': SOURCE_ID,
        'sourceName': SOURCE_NAME,
        'sourceUrl': url,
        'grantUrl': url,
        'title': 'Error',
        'eligibility': [],
        'fundingAmount': {'min': 0, 'max': 0, 'currency': 'CZK'},
        'deadline': None,
        'status': 'error',
        'statusNotes': error_message,
        'extractedAt': datetime.now(timezone.utc).isoformat(),
        'contentHash': '',
    }

    await dataset.push_data(error_record)


async def store_run_summary(mode: str, scraped: int, results: int, errors: int) -> None:
    """Store run summary in KV Store"""
    summary = {
        'mode': mode,
        'scraped': scraped,
        'results': results,
        'errors': errors,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }

    await Actor.set_value('runSummary', summary)
    Actor.log.info(f"Stored run summary: {summary}")


def main():
    asyncio.run(run_actor())


if __name__ == '__main__':
    main()
