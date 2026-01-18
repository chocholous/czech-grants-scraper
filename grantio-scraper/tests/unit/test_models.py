"""Tests for core models."""

import pytest
from datetime import datetime, timezone

from grants_scraper.core.models import (
    Grant,
    Document,
    GrantTarget,
    FundingAmount,
    GrantType,
    GrantStatus,
)


class TestFundingAmount:
    """Tests for FundingAmount dataclass."""

    def test_to_dict_all_fields(self):
        """Test to_dict with all fields populated."""
        amount = FundingAmount(
            min=100000,
            max=500000,
            total=10000000,
            currency="CZK",
        )
        result = amount.to_dict()

        assert result["min"] == 100000
        assert result["max"] == 500000
        assert result["total"] == 10000000
        assert result["currency"] == "CZK"

    def test_to_dict_partial_fields(self):
        """Test to_dict with some fields None."""
        amount = FundingAmount(max=500000)
        result = amount.to_dict()

        assert "min" not in result
        assert result["max"] == 500000
        assert "total" not in result
        assert result["currency"] == "CZK"


class TestDocument:
    """Tests for Document dataclass."""

    def test_basic_document(self):
        """Test basic document creation."""
        doc = Document(
            title="Výzva 2024",
            url="https://example.com/vyzva.pdf",
            doc_type="call_text",
            file_format="pdf",
        )

        assert doc.title == "Výzva 2024"
        assert doc.doc_type == "call_text"
        assert doc.file_format == "pdf"

    def test_to_dict_excludes_none(self):
        """Test that to_dict excludes None values."""
        doc = Document(
            title="Test",
            url="https://example.com/test.pdf",
            doc_type="other",
            file_format="pdf",
        )
        result = doc.to_dict()

        assert "size" not in result
        assert "local_path" not in result
        assert result["title"] == "Test"


class TestGrantTarget:
    """Tests for GrantTarget dataclass."""

    def test_basic_target(self):
        """Test basic target creation."""
        target = GrantTarget(
            url="https://example.com/grant/1",
            title="Test Grant",
            source_id="test_source",
        )

        assert target.url == "https://example.com/grant/1"
        assert target.title == "Test Grant"
        assert target.source_id == "test_source"

    def test_target_with_metadata(self):
        """Test target with extra metadata."""
        target = GrantTarget(
            url="https://example.com/grant/1",
            source_id="test",
            metadata={"page": 1, "category": "health"},
        )

        assert target.metadata["page"] == 1
        assert target.metadata["category"] == "health"


class TestGrant:
    """Tests for Grant dataclass."""

    def test_minimal_grant(self):
        """Test grant with minimal required fields."""
        grant = Grant(
            source_id="test",
            source_name="Test Source",
            source_url="https://example.com",
            grant_url="https://example.com/grant/1",
            title="Test Grant",
        )

        assert grant.source_id == "test"
        assert grant.title == "Test Grant"
        assert grant.grant_type == GrantType.CALL
        assert grant.status == GrantStatus.OK

    def test_grant_with_funding(self):
        """Test grant with funding information."""
        grant = Grant(
            source_id="test",
            source_name="Test Source",
            source_url="https://example.com",
            grant_url="https://example.com/grant/1",
            title="Test Grant",
            funding_amount=FundingAmount(min=100000, max=500000),
        )

        assert grant.funding_amount is not None
        assert grant.funding_amount.min == 100000
        assert grant.funding_amount.max == 500000

    def test_to_dict_datetime_serialization(self):
        """Test that datetimes are serialized to ISO format."""
        deadline = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        grant = Grant(
            source_id="test",
            source_name="Test",
            source_url="https://example.com",
            grant_url="https://example.com/1",
            title="Test",
            deadline=deadline,
        )

        result = grant.to_dict()
        assert result["deadline"] == "2024-12-31T23:59:59+00:00"

    def test_to_prd_schema(self):
        """Test PRD schema conversion."""
        grant = Grant(
            source_id="test",
            source_name="Test Source",
            source_url="https://example.com",
            grant_url="https://example.com/grant/1",
            title="Test Grant",
            description="This is a test grant",
            funding_amount=FundingAmount(min=100000, max=500000),
            deadline=datetime(2024, 12, 31, tzinfo=timezone.utc),
        )

        schema = grant.to_prd_schema()

        assert schema["recordType"] == "grant"
        assert schema["sourceId"] == "test"
        assert schema["title"] == "Test Grant"
        assert schema["fundingAmount"]["min"] == 100000
        assert schema["deadline"] == "2024-12-31T00:00:00+00:00"
