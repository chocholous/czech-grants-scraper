"""Základní testy pro scrapery."""

import pytest


def test_imports():
    """Test že základní importy fungují."""
    from scrapers.grants.sources import models
    from scrapers.grants.sources import base
    from scrapers.grants.sources import registry

    assert models is not None
    assert base is not None
    assert registry is not None


def test_grant_model():
    """Test vytvoření GrantContent modelu."""
    from scrapers.grants.sources.models import GrantContent

    content = GrantContent(
        source_url="https://example.cz/grant/1",
        scraper_name="TestScraper",
    )

    assert content.source_url == "https://example.cz/grant/1"
    assert content.scraper_name == "TestScraper"


def test_new_source_imports():
    """Test že nové zdroje lze importovat."""
    from scrapers.grants.sources.gacr_cz import GACRCzScraper
    from scrapers.grants.sources.tacr_cz import TACRCzScraper
    from scrapers.grants.sources.azvcr_cz import AZVCRCzScraper

    assert GACRCzScraper().can_handle("https://gacr.cz")
    assert TACRCzScraper().can_handle("https://tacr.cz")
    assert AZVCRCzScraper().can_handle("https://azvcr.cz")


# Přidejte další testy pro jednotlivé scrapery
