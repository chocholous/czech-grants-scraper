"""Tests for deduplicator functionality."""

import pytest
from datetime import datetime, timezone

from grants_scraper.core.deduplicator import (
    generate_content_hash,
    Deduplicator,
    DeduplicationResult,
)
from grants_scraper.core.models import Grant, GrantType, GrantStatus


class TestGenerateContentHash:
    """Tests for generate_content_hash function."""

    def test_consistent_hash(self):
        """Test that same inputs produce same hash."""
        hash1 = generate_content_hash(
            source_id="test",
            url="https://example.com/grant/1",
            title="Test Grant",
            deadline="2024-12-31",
        )
        hash2 = generate_content_hash(
            source_id="test",
            url="https://example.com/grant/1",
            title="Test Grant",
            deadline="2024-12-31",
        )

        assert hash1 == hash2

    def test_different_inputs_different_hash(self):
        """Test that different inputs produce different hashes."""
        hash1 = generate_content_hash(
            source_id="test",
            url="https://example.com/grant/1",
            title="Test Grant",
        )
        hash2 = generate_content_hash(
            source_id="test",
            url="https://example.com/grant/2",
            title="Test Grant",
        )

        assert hash1 != hash2

    def test_url_normalization(self):
        """Test that URLs are normalized (trailing slash)."""
        hash1 = generate_content_hash(
            source_id="test",
            url="https://example.com/grant/",
            title="Test",
        )
        hash2 = generate_content_hash(
            source_id="test",
            url="https://example.com/grant",
            title="Test",
        )

        assert hash1 == hash2

    def test_case_normalization(self):
        """Test that case is normalized."""
        hash1 = generate_content_hash(
            source_id="test",
            url="HTTPS://EXAMPLE.COM/GRANT",
            title="Test Grant",
        )
        hash2 = generate_content_hash(
            source_id="test",
            url="https://example.com/grant",
            title="test grant",
        )

        assert hash1 == hash2


class TestDeduplicator:
    """Tests for Deduplicator class."""

    def create_grant(
        self,
        source_id: str = "test",
        url: str = "https://example.com/grant/1",
        title: str = "Test Grant",
    ) -> Grant:
        """Helper to create test grants."""
        return Grant(
            source_id=source_id,
            source_name="Test Source",
            source_url="https://example.com",
            grant_url=url,
            title=title,
        )

    def test_check_not_duplicate(self):
        """Test checking a new grant."""
        dedup = Deduplicator()
        grant = self.create_grant()

        result = dedup.check(grant)

        assert result.is_duplicate is False
        assert result.action == "keep"

    def test_check_duplicate(self):
        """Test checking a duplicate grant."""
        dedup = Deduplicator()
        grant1 = self.create_grant()
        grant2 = self.create_grant()

        dedup.add(grant1)
        result = dedup.check(grant2)

        assert result.is_duplicate is True

    def test_add_and_check(self):
        """Test adding grants and checking count."""
        dedup = Deduplicator()

        dedup.add(self.create_grant(url="https://example.com/1"))
        dedup.add(self.create_grant(url="https://example.com/2"))
        dedup.add(self.create_grant(url="https://example.com/3"))

        assert len(dedup) == 3

    def test_process_keeps_new(self):
        """Test process keeps new grants."""
        dedup = Deduplicator()
        grant = self.create_grant()

        result = dedup.process(grant)

        assert result is not None
        assert result.title == "Test Grant"
        assert len(dedup) == 1

    def test_process_skips_duplicate(self):
        """Test process skips duplicates."""
        dedup = Deduplicator()
        grant1 = self.create_grant()
        grant2 = self.create_grant()

        dedup.process(grant1)
        result = dedup.process(grant2)

        assert result is None
        assert len(dedup) == 1

    def test_get_all(self):
        """Test getting all unique grants."""
        dedup = Deduplicator()

        dedup.process(self.create_grant(url="https://example.com/1", title="Grant 1"))
        dedup.process(self.create_grant(url="https://example.com/2", title="Grant 2"))
        dedup.process(self.create_grant(url="https://example.com/1", title="Grant 1"))  # Duplicate

        grants = dedup.get_all()
        assert len(grants) == 2

    def test_clear(self):
        """Test clearing the deduplicator."""
        dedup = Deduplicator()
        dedup.add(self.create_grant())

        assert len(dedup) == 1

        dedup.clear()

        assert len(dedup) == 0

    def test_merge_higher_priority(self):
        """Test merging when new source has higher priority."""
        dedup = Deduplicator()

        # Lower priority source
        grant1 = Grant(
            source_id="dotaceeu",  # Priority 10
            source_name="dotaceeu.cz",
            source_url="https://dotaceeu.cz",
            grant_url="https://example.com/grant/1",
            title="Test Grant",
            description="Basic description",
        )

        # Higher priority source
        grant2 = Grant(
            source_id="mzd_gov",  # Priority 30
            source_name="MZD",
            source_url="https://mzd.gov.cz",
            grant_url="https://example.com/grant/1",
            title="Test Grant",
            description="Detailed description",
        )

        dedup.process(grant1)
        dedup.process(grant2)

        grants = dedup.get_all()
        assert len(grants) == 1

        # Should have merged, preferring higher priority data
        merged = grants[0]
        assert merged.description == "Detailed description"
