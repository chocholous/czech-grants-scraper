"""Tests for normalizer functions."""

import pytest
from datetime import datetime

from grants_scraper.core.normalizer import (
    parse_czech_date,
    parse_czech_amount,
    normalize_title,
    cleanup_html_text,
    extract_funding_amounts,
    extract_email,
    extract_phone,
)


class TestParseCzechDate:
    """Tests for parse_czech_date function."""

    def test_standard_format(self):
        """Test standard Czech date format."""
        result = parse_czech_date("31. 12. 2024")
        assert result == datetime(2024, 12, 31)

    def test_compact_format(self):
        """Test compact format without spaces."""
        result = parse_czech_date("31.12.2024")
        assert result == datetime(2024, 12, 31)

    def test_single_digit_day_month(self):
        """Test single-digit day and month."""
        result = parse_czech_date("1. 5. 2024")
        assert result == datetime(2024, 5, 1)

    def test_date_in_text(self):
        """Test extracting date from text."""
        result = parse_czech_date("Uzávěrka: 15. 6. 2024 v 12:00")
        assert result == datetime(2024, 6, 15)

    def test_invalid_date(self):
        """Test invalid date returns None."""
        result = parse_czech_date("32. 13. 2024")
        assert result is None

    def test_empty_string(self):
        """Test empty string returns None."""
        result = parse_czech_date("")
        assert result is None

    def test_none_input(self):
        """Test None input returns None."""
        result = parse_czech_date(None)
        assert result is None


class TestParseCzechAmount:
    """Tests for parse_czech_amount function."""

    def test_millions_with_comma(self):
        """Test millions with comma decimal."""
        result = parse_czech_amount("1,5 mil. Kč")
        assert result == 1_500_000

    def test_millions_with_dot(self):
        """Test millions with dot decimal."""
        result = parse_czech_amount("2.5 mil")
        assert result == 2_500_000

    def test_plain_number_with_spaces(self):
        """Test plain number with space separators."""
        result = parse_czech_amount("1 000 000 Kč")
        assert result == 1_000_000

    def test_billions(self):
        """Test billions."""
        result = parse_czech_amount("1,5 mld. Kč")
        assert result == 1_500_000_000

    def test_thousands(self):
        """Test thousands."""
        result = parse_czech_amount("500 tis. Kč")
        assert result == 500_000

    def test_plain_number(self):
        """Test plain number without suffix."""
        result = parse_czech_amount("500000")
        assert result == 500_000

    def test_with_czk(self):
        """Test with CZK suffix."""
        result = parse_czech_amount("100000 CZK")
        assert result == 100_000

    def test_empty_string(self):
        """Test empty string returns None."""
        result = parse_czech_amount("")
        assert result is None


class TestNormalizeTitle:
    """Tests for normalize_title function."""

    def test_removes_extra_whitespace(self):
        """Test removal of extra whitespace."""
        result = normalize_title("Test   Grant    Title")
        assert result == "Test Grant Title"

    def test_strips_whitespace(self):
        """Test stripping leading/trailing whitespace."""
        result = normalize_title("  Test Grant  ")
        assert result == "Test Grant"

    def test_empty_string(self):
        """Test empty string."""
        result = normalize_title("")
        assert result == ""

    def test_none_input(self):
        """Test None input."""
        result = normalize_title(None)
        assert result == ""


class TestCleanupHtmlText:
    """Tests for cleanup_html_text function."""

    def test_removes_html_entities(self):
        """Test removal of HTML entities."""
        result = cleanup_html_text("Test&nbsp;text&amp;more")
        assert result == "Test text&more"

    def test_normalizes_whitespace(self):
        """Test whitespace normalization."""
        result = cleanup_html_text("Test    \t  text")
        assert result == "Test text"

    def test_fixes_punctuation_spacing(self):
        """Test punctuation spacing fix."""
        result = cleanup_html_text("Hello , world")
        assert result == "Hello, world"


class TestExtractFundingAmounts:
    """Tests for extract_funding_amounts function."""

    def test_extracts_all_amounts(self):
        """Test extraction of all amount types."""
        text = """
        Minimální částka: 100 000 Kč
        Maximální částka: 5 mil. Kč
        Celková alokace: 50 mil. Kč
        """
        result = extract_funding_amounts(text)

        assert result["min"] == 100_000
        assert result["max"] == 5_000_000
        assert result["total"] == 50_000_000
        assert result["currency"] == "CZK"

    def test_partial_amounts(self):
        """Test with only some amounts present."""
        text = "maximální částka: 1 mil. Kč"
        result = extract_funding_amounts(text)

        assert result["min"] is None
        assert result["max"] == 1_000_000
        assert result["total"] is None


class TestExtractEmail:
    """Tests for extract_email function."""

    def test_simple_email(self):
        """Test simple email extraction."""
        result = extract_email("Kontakt: info@example.com")
        assert result == "info@example.com"

    def test_no_email(self):
        """Test when no email present."""
        result = extract_email("Žádný kontakt")
        assert result is None


class TestExtractPhone:
    """Tests for extract_phone function."""

    def test_czech_format_with_prefix(self):
        """Test Czech phone with +420 prefix."""
        result = extract_phone("Telefon: +420 123 456 789")
        assert result == "+420123456789"

    def test_no_phone(self):
        """Test when no phone present."""
        result = extract_phone("Bez telefonu")
        assert result is None
