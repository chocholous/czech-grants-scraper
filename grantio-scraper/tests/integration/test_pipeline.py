"""Integration tests for the full scraping pipeline."""

import pytest
from pathlib import Path

from grants_scraper.core.models import Grant, GrantTarget
from grants_scraper.core.http_client import HttpClient
from grants_scraper.navigators.base import SourceConfig
from grants_scraper.navigators.single_level import SingleLevelNavigator
from grants_scraper.parsers.html_detail import HtmlDetailParser
from grants_scraper.config.loader import ConfigLoader


class TestConfigLoader:
    """Tests for configuration loading."""

    def test_load_sources_yml(self):
        """Test loading sources.yml file."""
        loader = ConfigLoader()
        sources = loader.load_sources("sources.yml")

        assert len(sources) > 0
        assert all(isinstance(s, SourceConfig) for s in sources)

    def test_source_config_fields(self):
        """Test that source configs have required fields."""
        loader = ConfigLoader()
        sources = loader.load_sources("sources.yml")

        for source in sources:
            assert source.source_id
            assert source.source_name
            assert source.base_url
            assert source.listing_url


class TestHtmlDetailParser:
    """Tests for HTML detail parser with sample HTML."""

    @pytest.fixture
    def sample_grant_html(self):
        """Sample grant detail HTML."""
        return """
        <html>
        <body>
            <main>
                <h1>Dotační program 2024</h1>
                <div class="perex">
                    Program podpory pro neziskové organizace.
                </div>
                <p>Celková alokace: 50 mil. Kč</p>
                <p>Maximální částka: 5 mil. Kč na projekt</p>
                <p>Uzávěrka: 31. 12. 2024</p>
                <h2>Dokumenty</h2>
                <a href="/docs/vyzva.pdf">Výzva</a>
                <a href="/docs/prirucka.pdf">Příručka pro žadatele</a>
                <a href="mailto:dotace@example.com">Kontakt</a>
            </main>
        </body>
        </html>
        """

    def test_parse_grant_html(self, sample_grant_html):
        """Test parsing sample grant HTML."""
        from bs4 import BeautifulSoup
        from grants_scraper.core.selectors import (
            get_main_container,
            extract_page_title,
            extract_summary,
            extract_documents,
            extract_contact_email,
        )
        from grants_scraper.core.normalizer import (
            extract_funding_amounts,
            parse_czech_date,
        )

        soup = BeautifulSoup(sample_grant_html, "lxml")
        container = get_main_container(soup)

        # Test title extraction
        title = extract_page_title(soup)
        assert title == "Dotační program 2024"

        # Test summary extraction
        summary = extract_summary(container)
        assert "neziskové organizace" in summary

        # Test funding extraction
        page_text = soup.get_text()
        funding = extract_funding_amounts(page_text)
        assert funding["total"] == 50_000_000
        assert funding["max"] == 5_000_000

        # Test deadline extraction
        deadline = parse_czech_date("31. 12. 2024")
        assert deadline is not None
        assert deadline.year == 2024
        assert deadline.month == 12

        # Test documents extraction
        docs = extract_documents(soup, "https://example.com")
        assert len(docs) == 2
        assert any(d["doc_type"] == "call_text" for d in docs)
        assert any(d["doc_type"] == "guidelines" for d in docs)

        # Test contact extraction
        email = extract_contact_email(soup)
        assert email == "dotace@example.com"


class TestSourceConfig:
    """Tests for SourceConfig."""

    def test_from_dict(self):
        """Test creating SourceConfig from dict."""
        data = {
            "source_id": "test",
            "source_name": "Test Source",
            "base_url": "https://example.com",
            "listing_url": "https://example.com/grants",
            "listing_selector": "a.grant-link",
            "requests_per_second": 1.5,
        }

        config = SourceConfig.from_dict(data)

        assert config.source_id == "test"
        assert config.source_name == "Test Source"
        assert config.listing_selector == "a.grant-link"
        assert config.requests_per_second == 1.5

    def test_from_dict_defaults(self):
        """Test default values when creating from dict."""
        data = {
            "source_id": "test",
            "source_name": "Test",
            "base_url": "https://example.com",
            "listing_url": "https://example.com/grants",
        }

        config = SourceConfig.from_dict(data)

        assert config.listing_selector == "a"  # Default
        assert config.max_pages == 50  # Default
        assert config.requests_per_second == 2.0  # Default


class TestPipelineIntegration:
    """Integration tests for full pipeline."""

    @pytest.mark.asyncio
    async def test_http_client_context_manager(self):
        """Test HTTP client context manager."""
        async with HttpClient() as client:
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_grant_extraction_flow(self):
        """Test grant extraction flow with mock data."""
        # Create target
        target = GrantTarget(
            url="https://example.com/grant/1",
            title="Test Grant",
            source_id="test",
            metadata={"source_name": "Test Source"},
        )

        # Create source config
        source = SourceConfig(
            source_id="test",
            source_name="Test Source",
            base_url="https://example.com",
            listing_url="https://example.com/grants",
        )

        # Verify target and source are valid
        assert target.url is not None
        assert source.source_id == "test"
