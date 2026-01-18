"""
YAML configuration loader with validation.

Loads source definitions from YAML files with:
- Environment variable substitution
- Schema validation
- Default values
"""

import os
import re
from pathlib import Path
from typing import Optional

import yaml
import structlog

from grants_scraper.navigators.base import SourceConfig

logger = structlog.get_logger(__name__)


def substitute_env_vars(text: str) -> str:
    """
    Substitute environment variables in text.

    Supports formats:
    - ${VAR_NAME} - required, error if missing
    - ${VAR_NAME:-default} - optional with default

    Args:
        text: Text with env var placeholders

    Returns:
        Text with substituted values
    """
    def replace(match):
        var_expr = match.group(1)
        if ":-" in var_expr:
            var_name, default = var_expr.split(":-", 1)
            return os.getenv(var_name, default)
        else:
            value = os.getenv(var_expr)
            if value is None:
                logger.warning("env_var_not_set", var=var_expr)
                return ""
            return value

    return re.sub(r"\$\{([^}]+)\}", replace, text)


class ConfigLoader:
    """
    Configuration loader for grant sources.

    Loads YAML config files and validates against expected schema.
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize config loader.

        Args:
            config_dir: Directory containing config files
                       (defaults to package config directory)
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path(__file__).parent

    def load_file(self, filename: str) -> dict:
        """
        Load YAML config file.

        Args:
            filename: Config file name (relative to config_dir)

        Returns:
            Parsed config dict
        """
        filepath = self.config_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Config file not found: {filepath}")

        logger.info("loading_config", file=str(filepath))

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Substitute environment variables
        content = substitute_env_vars(content)

        # Parse YAML
        config = yaml.safe_load(content)

        return config or {}

    def load_sources(self, filename: str = "sources.yml") -> list[SourceConfig]:
        """
        Load source definitions from YAML.

        Args:
            filename: Sources config file name

        Returns:
            List of SourceConfig objects
        """
        config = self.load_file(filename)

        sources = []
        for source_data in config.get("sources", []):
            try:
                source = self._parse_source(source_data)
                sources.append(source)
                logger.info("source_loaded", source_id=source.source_id)
            except Exception as e:
                logger.error(
                    "source_load_failed",
                    source=source_data.get("source_id", "unknown"),
                    error=str(e),
                )

        return sources

    def _parse_source(self, data: dict) -> SourceConfig:
        """
        Parse source definition into SourceConfig.

        Args:
            data: Source definition dict

        Returns:
            SourceConfig object

        Raises:
            ValueError: If required fields missing
        """
        required = ["source_id", "source_name", "base_url", "listing_url"]
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        return SourceConfig(
            source_id=data["source_id"],
            source_name=data["source_name"],
            base_url=data["base_url"],
            listing_url=data["listing_url"],
            listing_selector=data.get("listing_selector", "a"),
            detail_url_pattern=data.get("detail_url_pattern"),
            pagination_selector=data.get("pagination_selector"),
            max_pages=data.get("max_pages", 50),
            requests_per_second=data.get("requests_per_second", 2.0),
            metadata=data.get("metadata", {}),
        )


def load_sources(config_path: Optional[str] = None) -> list[SourceConfig]:
    """
    Convenience function to load source configs.

    Args:
        config_path: Optional path to sources.yml

    Returns:
        List of SourceConfig objects
    """
    if config_path:
        config_dir = str(Path(config_path).parent)
        filename = Path(config_path).name
        loader = ConfigLoader(config_dir)
        return loader.load_sources(filename)
    else:
        loader = ConfigLoader()
        return loader.load_sources()
