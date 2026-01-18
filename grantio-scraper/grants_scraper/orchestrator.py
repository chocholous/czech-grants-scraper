"""
Master orchestrator for the grants scraping pipeline.

Coordinates:
- Source configuration loading
- Navigator selection and execution
- Parser execution
- Deduplication
- Output generation
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from .core.models import Grant
from .core.http_client import HttpClient
from .core.deduplicator import Deduplicator
from .config.loader import ConfigLoader, load_sources
from .navigators.base import SourceConfig, NavigatorStrategy
from .navigators.single_level import SingleLevelNavigator
from .navigators.multi_level import MultiLevelNavigator
from .navigators.static import StaticNavigator
from .parsers.base import ParserStrategy
from .parsers.html_detail import HtmlDetailParser

logger = structlog.get_logger(__name__)


class MasterScraper:
    """
    Master orchestrator for the scraping pipeline.

    Coordinates discovery, extraction, deduplication, and output.
    """

    # Navigator registry
    NAVIGATORS = {
        "single_level": SingleLevelNavigator,
        "multi_level": MultiLevelNavigator,
        "static": StaticNavigator,
    }

    # Parser registry
    PARSERS = {
        "html_detail": HtmlDetailParser,
    }

    def __init__(
        self,
        config_path: Optional[str] = None,
        output_dir: str = "output",
        requests_per_second: float = 2.0,
    ):
        """
        Initialize master scraper.

        Args:
            config_path: Path to sources.yml
            output_dir: Directory for output files
            requests_per_second: Default rate limit
        """
        self.config_path = config_path
        self.output_dir = Path(output_dir)
        self.requests_per_second = requests_per_second

        self.deduplicator = Deduplicator()
        self.http_client: Optional[HttpClient] = None

        # Statistics
        self.stats = {
            "sources_processed": 0,
            "grants_discovered": 0,
            "grants_extracted": 0,
            "grants_deduplicated": 0,
            "errors": 0,
        }

    async def run(
        self,
        sources: Optional[list[str]] = None,
        max_grants: Optional[int] = None,
        dry_run: bool = False,
    ) -> list[Grant]:
        """
        Run the scraping pipeline.

        Args:
            sources: Optional list of source_ids to process (None = all)
            max_grants: Optional limit per source
            dry_run: If True, only discover without extracting

        Returns:
            List of extracted grants
        """
        logger.info(
            "starting_scrape",
            sources=sources or "all",
            max_grants=max_grants,
            dry_run=dry_run,
        )

        # Load source configurations
        source_configs = self._load_sources(sources)

        if not source_configs:
            logger.warning("no_sources_to_process")
            return []

        logger.info("sources_loaded", count=len(source_configs))

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        all_grants: list[Grant] = []

        # Initialize shared HTTP client
        self.http_client = HttpClient(
            requests_per_second=self.requests_per_second,
        )

        async with self.http_client:
            for source in source_configs:
                try:
                    grants = await self._process_source(
                        source=source,
                        max_grants=max_grants,
                        dry_run=dry_run,
                    )
                    all_grants.extend(grants)
                    self.stats["sources_processed"] += 1
                except Exception as e:
                    logger.error(
                        "source_processing_failed",
                        source=source.source_id,
                        error=str(e),
                    )
                    self.stats["errors"] += 1

        # Deduplication
        unique_grants = self.deduplicator.get_all()
        self.stats["grants_deduplicated"] = len(all_grants) - len(unique_grants)

        logger.info(
            "scrape_complete",
            **self.stats,
        )

        return unique_grants

    async def _process_source(
        self,
        source: SourceConfig,
        max_grants: Optional[int],
        dry_run: bool,
    ) -> list[Grant]:
        """
        Process a single source.

        Args:
            source: Source configuration
            max_grants: Optional limit
            dry_run: Discovery only

        Returns:
            List of extracted grants
        """
        logger.info(
            "processing_source",
            source=source.source_id,
            name=source.source_name,
        )

        # Get navigator
        navigator_type = source.metadata.get("navigator", "single_level")
        navigator_class = self.NAVIGATORS.get(navigator_type, SingleLevelNavigator)
        navigator = navigator_class(http_client=self.http_client)

        # Discovery phase
        targets = await navigator.discover(source, max_grants)
        self.stats["grants_discovered"] += len(targets)

        logger.info(
            "discovery_complete",
            source=source.source_id,
            targets=len(targets),
        )

        if dry_run:
            # Just print discovered URLs
            for target in targets:
                logger.info(
                    "discovered_target",
                    url=target.url,
                    title=target.title,
                )
            return []

        # Get parser
        parser_type = source.metadata.get("parser", "html_detail")
        parser_class = self.PARSERS.get(parser_type, HtmlDetailParser)
        parser = parser_class(http_client=self.http_client)

        # Extraction phase
        grants = []
        for i, target in enumerate(targets):
            logger.info(
                "extracting",
                source=source.source_id,
                index=i + 1,
                total=len(targets),
                url=target.url,
            )

            try:
                grant = await parser.extract(target, source)
                if grant:
                    # Deduplication
                    processed = self.deduplicator.process(grant)
                    if processed:
                        grants.append(processed)
                        self.stats["grants_extracted"] += 1
            except Exception as e:
                logger.error(
                    "extraction_failed",
                    url=target.url,
                    error=str(e),
                )
                self.stats["errors"] += 1

        return grants

    def _load_sources(
        self,
        source_ids: Optional[list[str]],
    ) -> list[SourceConfig]:
        """
        Load and filter source configurations.

        Args:
            source_ids: Optional list of source_ids to include

        Returns:
            Filtered list of SourceConfig
        """
        all_sources = load_sources(self.config_path)

        if source_ids:
            return [s for s in all_sources if s.source_id in source_ids]

        return all_sources

    def save_json(self, grants: list[Grant], filename: Optional[str] = None) -> str:
        """
        Save grants to JSON file.

        Args:
            grants: List of grants to save
            filename: Optional filename (auto-generated if not provided)

        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"grants_{timestamp}.json"

        filepath = self.output_dir / filename

        data = [g.to_prd_schema() for g in grants]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("saved_json", path=str(filepath), grants=len(grants))
        return str(filepath)

    def save_jsonl(self, grants: list[Grant], filename: Optional[str] = None) -> str:
        """
        Save grants to JSONL file (one JSON per line).

        Args:
            grants: List of grants to save
            filename: Optional filename

        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"grants_{timestamp}.jsonl"

        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for grant in grants:
                line = json.dumps(grant.to_prd_schema(), ensure_ascii=False)
                f.write(line + "\n")

        logger.info("saved_jsonl", path=str(filepath), grants=len(grants))
        return str(filepath)


async def run_scraper(
    sources: Optional[list[str]] = None,
    max_grants: Optional[int] = None,
    dry_run: bool = False,
    config_path: Optional[str] = None,
    output_dir: str = "output",
) -> list[Grant]:
    """
    Convenience function to run the scraper.

    Args:
        sources: Optional source_ids to process
        max_grants: Optional limit per source
        dry_run: Discovery only
        config_path: Path to sources.yml
        output_dir: Output directory

    Returns:
        List of extracted grants
    """
    scraper = MasterScraper(
        config_path=config_path,
        output_dir=output_dir,
    )

    grants = await scraper.run(
        sources=sources,
        max_grants=max_grants,
        dry_run=dry_run,
    )

    if grants and not dry_run:
        scraper.save_json(grants)

    return grants
