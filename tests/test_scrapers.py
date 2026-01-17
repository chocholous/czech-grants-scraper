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
    """Test vytvoření Grant modelu."""
    from scrapers.grants.sources.models import Grant

    grant = Grant(
        title="Test Grant",
        source="https://example.cz",
        url="https://example.cz/grant/1",
    )

    assert grant.title == "Test Grant"
    assert grant.source == "https://example.cz"


# Přidejte další testy pro jednotlivé scrapery
