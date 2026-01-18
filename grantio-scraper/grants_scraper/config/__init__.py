"""
Configuration module for grant sources.

Provides:
- YAML config loading with validation
- Source definitions
- Environment variable substitution
"""

from .loader import ConfigLoader, load_sources

__all__ = ["ConfigLoader", "load_sources"]
