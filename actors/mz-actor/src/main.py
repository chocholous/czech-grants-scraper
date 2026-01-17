"""
Main entry point for MZ Grants Scraper Actor.

Orchestrates execution modes:
- search: Query existing dataset
- refresh: Force scrape all sources
- auto: Scrape if stale, then search
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from apify import Actor

from .scraper import MZScraper
from .mapper import map_to_prd_schema, validate_prd_record
from .storage import DatasetManager, KVStoreManager
from .utils import is_date_in_past


# Source metadata
SOURCE_ID = "mz-grants"
SOURCE_NAME = "Ministerstvo zdravotnictví"


async def main():
    """Main actor entry point"""
    async with Actor:
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
            await Actor.fail(status_message=f"Invalid mode: {mode}")
            return

        # Initialize managers
        dataset_mgr = DatasetManager()
        kv_mgr = KVStoreManager()

        Actor.log.info(f"Mode: {mode}, onlyActive: {only_active}, staleAfterDays: {stale_after_days}")

        # Execute based on mode
        try:
            if mode == 'search':
                results = await search_mode(dataset_mgr, actor_input)
                await store_run_summary(kv_mgr, mode, scraped=0, results=len(results), errors=0)

            elif mode == 'refresh':
                scraped, errors = await refresh_mode(dataset_mgr, kv_mgr)
                results = await search_mode(dataset_mgr, actor_input)
                await store_run_summary(kv_mgr, mode, scraped=scraped, results=len(results), errors=errors)

            elif mode == 'auto':
                # Check staleness
                last_fetched = await kv_mgr.get_last_fetched(SOURCE_ID)
                is_stale = check_staleness(last_fetched, stale_after_days)

                Actor.log.info(f"Last fetched: {last_fetched}, is_stale: {is_stale}")

                if is_stale:
                    Actor.log.info("Data is stale, triggering refresh")
                    scraped, errors = await refresh_mode(dataset_mgr, kv_mgr)
                else:
                    Actor.log.info("Data is fresh, skipping scrape")
                    scraped, errors = 0, 0

                # Always return search results
                results = await search_mode(dataset_mgr, actor_input)
                await store_run_summary(kv_mgr, mode, scraped=scraped, results=len(results), errors=errors)

            Actor.log.info("Actor completed successfully")

        except Exception as e:
            Actor.log.exception(f"Actor failed with error: {e}")
            await Actor.fail(status_message=str(e))


async def refresh_mode(dataset_mgr: DatasetManager, kv_mgr: KVStoreManager) -> tuple[int, int]:
    """
    Refresh mode: Force scrape all sources.

    Args:
        dataset_mgr: Dataset manager
        kv_mgr: KV Store manager

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
                await push_error_record(dataset_mgr, url, "Failed to extract content")
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
            await dataset_mgr.push(prd_record)
            scraped_count += 1

            Actor.log.info(f"Successfully scraped: {prd_record.get('title', 'unknown')}")

        except Exception as e:
            Actor.log.error(f"Error scraping {url}: {e}")
            error_count += 1

            # Push error record
            await push_error_record(dataset_mgr, url, str(e))

    # Update lastFetchedAt timestamp
    await kv_mgr.set_last_fetched(SOURCE_ID, datetime.now(timezone.utc))

    Actor.log.info(f"Refresh completed: {scraped_count} scraped, {error_count} errors")
    return scraped_count, error_count


async def search_mode(dataset_mgr: DatasetManager, actor_input: Dict) -> List[Dict]:
    """
    Search mode: Query existing dataset.

    Args:
        dataset_mgr: Dataset manager
        actor_input: Actor input parameters

    Returns:
        List of matching grant records
    """
    Actor.log.info("Starting search mode")

    # Get all records
    all_records = await dataset_mgr.get_all()

    Actor.log.info(f"Loaded {len(all_records)} records from dataset")

    # Filter by source
    records = [r for r in all_records if r.get('sourceId') == SOURCE_ID]

    Actor.log.info(f"Filtered to {len(records)} MZ records")

    # Apply filters
    query = actor_input.get('query')
    only_active = actor_input.get('onlyActive', True)
    limit = actor_input.get('limit', 100)

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
    """
    Check if data is stale based on last fetch time.

    Args:
        last_fetched: Last fetch timestamp (or None if never fetched)
        stale_after_days: Number of days before data is considered stale

    Returns:
        True if data is stale, False otherwise
    """
    if not last_fetched:
        return True

    days_since_fetch = (datetime.now(timezone.utc) - last_fetched).days
    return days_since_fetch > stale_after_days


async def push_error_record(dataset_mgr: DatasetManager, url: str, error_message: str) -> None:
    """
    Push error record to dataset.

    Args:
        dataset_mgr: Dataset manager
        url: URL that failed
        error_message: Error description
    """
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

    await dataset_mgr.push(error_record)


async def store_run_summary(
    kv_mgr: KVStoreManager,
    mode: str,
    scraped: int,
    results: int,
    errors: int
) -> None:
    """
    Store run summary in KV Store.

    Args:
        kv_mgr: KV Store manager
        mode: Execution mode
        scraped: Number of grants scraped
        results: Number of results returned
        errors: Number of errors
    """
    summary = {
        'mode': mode,
        'scraped': scraped,
        'results': results,
        'errors': errors,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }

    await kv_mgr.set_run_summary(summary)


if __name__ == '__main__':
    asyncio.run(main())
