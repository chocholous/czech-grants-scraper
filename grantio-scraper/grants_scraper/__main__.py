"""
CLI entry point for grants-scraper.

Usage:
    python -m grants_scraper --mode full
    python -m grants_scraper --sources mzd_gov,mfcr
    python -m grants_scraper --dry-run --max-grants 5
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import structlog

# Log level mapping
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def setup_logging(level: str = "INFO", json_output: bool = False):
    """Configure structured logging."""
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)

    if json_output:
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Czech grants scraper with modular architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all configured sources
  python -m grants_scraper --mode full

  # Scrape specific sources
  python -m grants_scraper --sources mzd_gov,mfcr

  # Dry run (discovery only, no extraction)
  python -m grants_scraper --dry-run

  # Limit grants per source (for testing)
  python -m grants_scraper --sources mzd_gov --max-grants 5

  # Use custom config file
  python -m grants_scraper --config /path/to/sources.yml
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="full",
        help="Scraping mode: full (all grants) or incremental (new only)",
    )

    parser.add_argument(
        "--sources",
        type=str,
        help="Comma-separated list of source_ids to process (default: all)",
    )

    parser.add_argument(
        "--max-grants",
        type=int,
        help="Maximum grants to process per source (for testing)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discovery only - don't extract grant details",
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to sources.yml config file",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="output",
        help="Output directory (default: output)",
    )

    parser.add_argument(
        "--output-format",
        choices=["json", "jsonl", "both"],
        default="json",
        help="Output format (default: json)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--json-logs",
        action="store_true",
        help="Output logs as JSON (for production)",
    )

    parser.add_argument(
        "--rate-limit",
        type=float,
        default=2.0,
        help="Requests per second per domain (default: 2.0)",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    return parser.parse_args()


async def main_async(args):
    """Async main function."""
    from .orchestrator import MasterScraper

    logger = structlog.get_logger(__name__)

    logger.info(
        "starting_grants_scraper",
        mode=args.mode,
        sources=args.sources,
        max_grants=args.max_grants,
        dry_run=args.dry_run,
    )

    # Parse source list
    sources = None
    if args.sources:
        sources = [s.strip() for s in args.sources.split(",")]

    # Initialize scraper
    scraper = MasterScraper(
        config_path=args.config,
        output_dir=args.output,
        requests_per_second=args.rate_limit,
    )

    # Run scraping
    grants = await scraper.run(
        sources=sources,
        max_grants=args.max_grants,
        dry_run=args.dry_run,
    )

    # Save output
    if grants and not args.dry_run:
        if args.output_format in ["json", "both"]:
            scraper.save_json(grants)

        if args.output_format in ["jsonl", "both"]:
            scraper.save_jsonl(grants)

        logger.info(
            "scraping_complete",
            total_grants=len(grants),
            output_dir=args.output,
        )
    elif args.dry_run:
        logger.info(
            "dry_run_complete",
            discovered_grants=scraper.stats["grants_discovered"],
        )
    else:
        logger.warning("no_grants_extracted")

    return grants


def main():
    """Main entry point."""
    args = parse_args()

    # Version check
    if args.version:
        from . import __version__
        print(f"grants-scraper {__version__}")
        sys.exit(0)

    # Setup logging
    setup_logging(args.log_level, args.json_logs)

    # Run async main
    try:
        grants = asyncio.run(main_async(args))
        sys.exit(0 if grants or args.dry_run else 1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger = structlog.get_logger(__name__)
        logger.exception("fatal_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
