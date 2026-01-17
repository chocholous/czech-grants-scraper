import asyncio
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Dict, List, Optional

from apify import Actor
from dateutil import parser as date_parser

# Add scrapers directory to path for imports
SCRAPERS_DIR = Path(__file__).parent.parent / "scrapers" / "grants"
sys.path.insert(0, str(SCRAPERS_DIR))


class ReadinessHandler(BaseHTTPRequestHandler):
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
        return


def start_readiness_server() -> Optional[ThreadingHTTPServer]:
    port_env = os.getenv("APIFY_CONTAINER_PORT") or os.getenv("PORT") or "3000"
    try:
        port = int(port_env)
    except ValueError:
        port = 3000

    server = ThreadingHTTPServer(("0.0.0.0", port), ReadinessHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    Actor.log.info(f"Readiness server listening on port {port}")
    return server


def parse_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return date_parser.parse(str(value)).date()
    except (ValueError, TypeError):
        return None


def filter_items(
    items: List[Dict[str, Any]],
    query: Optional[str],
    categories: Optional[List[str]],
    regions: Optional[List[str]],
    eligibility: Optional[List[str]],
    funding_range: Optional[Dict[str, Any]],
    deadline_range: Optional[Dict[str, Any]],
    only_active: bool,
    limit: int,
) -> List[Dict[str, Any]]:
    def matches_query(item: Dict[str, Any]) -> bool:
        if not query:
            return True
        haystack = " ".join(
            str(item.get(field, "") or "")
            for field in ["title", "summary", "description"]
        ).lower()
        return query.lower() in haystack

    def matches_list(field: str, values: Optional[List[str]]) -> bool:
        if not values:
            return True
        item_values = item.get(field) or []
        if isinstance(item_values, str):
            item_values = [item_values]
        item_values = [str(v).lower() for v in item_values]
        return any(str(value).lower() in item_values for value in values)

    def matches_funding(item: Dict[str, Any]) -> bool:
        if not funding_range:
            return True
        amount = item.get("fundingAmount") or {}
        item_min = amount.get("min")
        item_max = amount.get("max")
        min_req = funding_range.get("min")
        max_req = funding_range.get("max")
        if min_req is not None and item_max is not None and item_max < min_req:
            return False
        if max_req is not None and item_min is not None and item_min > max_req:
            return False
        return True

    def matches_deadline(item: Dict[str, Any]) -> bool:
        if not deadline_range:
            return True
        deadline = parse_date(item.get("deadline"))
        start = parse_date(deadline_range.get("from"))
        end = parse_date(deadline_range.get("to"))
        if start and deadline and deadline < start:
            return False
        if end and deadline and deadline > end:
            return False
        return True

    filtered = []
    for item in items:
        if only_active and item.get("status") not in (None, "ok", "partial"):
            continue
        if not matches_query(item):
            continue
        if not matches_list("categories", categories):
            continue
        if not matches_list("regions", regions):
            continue
        if not matches_list("eligibility", eligibility):
            continue
        if not matches_funding(item):
            continue
        if not matches_deadline(item):
            continue
        filtered.append(item)
        if len(filtered) >= limit:
            break

    return filtered


async def run_actor():
    await Actor.init()

    readiness_server = start_readiness_server()
    input_data = await Actor.get_input() or {}

    mode = input_data.get("mode", "refresh")
    Actor.log.info(f"Actor mode: {mode}")

    if mode not in {"search", "refresh", "auto"}:
        Actor.log.warning(f"Unknown mode '{mode}', defaulting to search")
        mode = "search"

    results: List[Dict[str, Any]] = []

    # LLM enrichment settings
    enable_llm = input_data.get("enableLlm", False)
    llm_model = input_data.get("llmModel", "anthropic/claude-haiku-4.5")

    if enable_llm:
        Actor.log.info(f"LLM enrichment enabled with model: {llm_model}")

    # Test mode: run sub-scrapers directly on provided URLs
    test_urls = input_data.get("testUrls", [])
    if test_urls:
        Actor.log.info(f"Test mode: processing {len(test_urls)} URLs with sub-scrapers")
        try:
            from subscrapers import SubScraperRegistry
            from subscrapers.gacr_cz import GACRCzScraper
            from subscrapers.tacr_cz import TACRCzScraper
            from subscrapers.azvcr_cz import AZVCRCzScraper
            from subscrapers.opst_cz import OPSTCzScraper
            from subscrapers.opzp_cz import OPZPCzScraper
            from subscrapers.nrb_cz import NRBCzScraper
            from subscrapers.sfzp_cz import SFZPCzScraper
            from subscrapers.esfcr_cz import ESFCRCzScraper
            from subscrapers.mv_gov_cz import MVGovCzScraper
            from subscrapers.irop_mmr_cz import IROPGovCzScraper
            from subscrapers.optak_gov_cz import OPTAKGovCzScraper
            import logging
            logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

            # Register all sub-scrapers with LLM settings
            registry = SubScraperRegistry()
            registry.register(GACRCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            registry.register(TACRCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            registry.register(AZVCRCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            registry.register(OPSTCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            registry.register(OPZPCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            registry.register(NRBCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            registry.register(SFZPCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            registry.register(ESFCRCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            registry.register(MVGovCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            registry.register(IROPGovCzScraper(enable_llm=enable_llm, llm_model=llm_model))
            registry.register(OPTAKGovCzScraper(enable_llm=enable_llm, llm_model=llm_model))

            Actor.log.info(f"Registered {registry.count()} sub-scrapers: {registry.list_scrapers()}")

            dataset = await Actor.open_dataset(name="czech-grants")

            for url in test_urls:
                Actor.log.info(f"Testing URL: {url}")
                scraper = registry.get_scraper_for_url(url)
                if not scraper:
                    Actor.log.warning(f"No scraper found for URL: {url}")
                    continue

                Actor.log.info(f"Using scraper: {scraper.get_scraper_name()}")
                try:
                    content = await scraper.extract_content(url, {"title": "Test", "external_id": "test"})
                    if content:
                        Actor.log.info(f"Extracted content: {len(content.description or '')} chars description, {len(content.documents)} documents")
                        # Build data dict
                        data = {
                            "recordType": "grant",
                            "sourceId": scraper.get_scraper_name(),
                            "sourceUrl": url,
                            "description": content.description,
                            "summary": content.summary,
                            "documents": [{"title": d.title, "url": d.url, "type": d.doc_type} for d in content.documents],
                            "fundingAmounts": content.funding_amounts,
                            "applicationUrl": content.application_url,
                            "contactEmail": content.contact_email,
                            "eligibleRecipients": content.eligible_recipients,
                            "scrapedAt": content.scraped_at.isoformat() if content.scraped_at else None,
                        }
                        # Add LLM-enhanced data if available
                        if content.enhanced_info:
                            data["enhancedInfo"] = content.enhanced_info.to_dict()
                            Actor.log.info(f"LLM enrichment: {len(content.enhanced_info.eligibility_criteria)} criteria, {len(content.enhanced_info.thematic_keywords)} keywords")
                        # Push to dataset
                        await dataset.push_data(data)
                        Actor.log.info(f"Pushed content to dataset")
                    else:
                        Actor.log.warning(f"No content extracted from {url}")
                except Exception as e:
                    Actor.log.error(f"Error extracting from {url}: {e}")

        except Exception as e:
            Actor.log.error(f"Test mode error: {e}")
            import traceback
            Actor.log.error(traceback.format_exc())

    # Run refresh first (if needed) so search can use fresh data
    elif mode in {"refresh", "auto"}:
        Actor.log.info("Running scrapers to refresh data...")
        try:
            # Import scraper components (deferred to avoid import issues when not refreshing)
            from dotaceeu import DotaceuCrawler, load_config, setup_logging

            # Change to scrapers directory for relative paths in config
            original_cwd = os.getcwd()
            os.chdir(SCRAPERS_DIR)

            try:
                # Load scraper config
                config = load_config("config.yml")

                # Configure logging so scraper progress is visible
                setup_logging(config)

                # Get scraper options from input
                max_grants = input_data.get("maxGrants")  # Optional limit for testing
                deep_scrape = input_data.get("deepScrape", False)

                Actor.log.info(f"Starting dotaceeu.cz scraper (max_grants={max_grants}, deep_scrape={deep_scrape})")

                # Run the crawler
                crawler = DotaceuCrawler(config, deep_scrape=deep_scrape)
                await crawler.run(max_grants=max_grants)

                Actor.log.info(f"Scraping complete. Processed: {crawler.processed_count}, Errors: {crawler.error_count}")

            finally:
                os.chdir(original_cwd)

            # Push scraped grants to the dataset (after restoring cwd for correct storage path)
            dataset = await Actor.open_dataset(name="czech-grants")
            for grant in crawler.grants:
                grant_dict = grant.to_dict()
                # Add recordType for consistency with PRD schema
                grant_dict["recordType"] = "grant"
                grant_dict["sourceId"] = "dotaceeu"
                grant_dict["sourceName"] = "dotaceeu.cz"
                await dataset.push_data(grant_dict)

            Actor.log.info(f"Pushed {len(crawler.grants)} grants to dataset")

            # If only refreshing, return the scraped results
            if mode == "refresh":
                results = [g.to_dict() for g in crawler.grants]

        except Exception as e:
            Actor.log.error(f"Scraper error: {e}")
            import traceback
            Actor.log.error(traceback.format_exc())

    # Search mode (or auto after refresh) - skip if testUrls was used
    if not test_urls and mode in {"search", "auto"}:
        dataset = await Actor.open_dataset(name="czech-grants")
        limit = int(input_data.get("limit", 100))
        data = await dataset.get_data(limit=limit)
        items = data.items or []
        results = filter_items(
            items=items,
            query=input_data.get("query"),
            categories=input_data.get("categories"),
            regions=input_data.get("regions"),
            eligibility=input_data.get("eligibility"),
            funding_range=input_data.get("fundingRange"),
            deadline_range=input_data.get("deadlineRange"),
            only_active=bool(input_data.get("onlyActive", True)),
            limit=limit,
        )
        Actor.log.info(f"Search results: {len(results)} items")

    if readiness_server:
        readiness_server.shutdown()

    await Actor.exit()


def main():
    asyncio.run(run_actor())


if __name__ == "__main__":
    main()
