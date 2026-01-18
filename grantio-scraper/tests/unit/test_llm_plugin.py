"""Tests for LLM extraction plugin."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from grants_scraper.plugins.llm import (
    ExtractedGrantData,
    LLMExtractor,
    ClaudeProvider,
    OpenAIProvider,
    EXTRACTION_PROMPT,
)


class TestExtractedGrantData:
    """Tests for ExtractedGrantData dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        data = ExtractedGrantData()
        assert data.title is None
        assert data.currency == "CZK"
        assert data.eligibility == []
        assert data.confidence == 0.0

    def test_with_values(self):
        """Test data with all values."""
        data = ExtractedGrantData(
            title="Test Grant",
            summary="Test summary",
            deadline=datetime(2024, 12, 31),
            funding_min=100000,
            funding_max=5000000,
            eligibility=["NGO", "Obce"],
            confidence=0.9,
        )
        assert data.title == "Test Grant"
        assert data.deadline == datetime(2024, 12, 31)
        assert data.funding_min == 100000
        assert len(data.eligibility) == 2


class TestClaudeProvider:
    """Tests for Claude provider."""

    def test_is_available_without_key(self):
        """Test availability check without API key."""
        with patch.dict("os.environ", {}, clear=True):
            provider = ClaudeProvider(api_key=None)
            # Clear the env var check
            provider.api_key = None
            assert provider.is_available() is False

    def test_is_available_with_key(self):
        """Test availability check with API key."""
        provider = ClaudeProvider(api_key="test-key-123")
        assert provider.is_available() is True

    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        provider = ClaudeProvider(api_key="test")
        response = '''{
            "title": "Test Grant",
            "summary": "Test summary",
            "deadline": "2024-12-31",
            "funding_min": 100000,
            "funding_max": 5000000,
            "eligibility": ["NGO"],
            "confidence": 0.85
        }'''

        result = provider._parse_response(response)
        assert result.title == "Test Grant"
        assert result.deadline == datetime(2024, 12, 31)
        assert result.funding_min == 100000
        assert result.confidence == 0.85

    def test_parse_response_with_code_block(self):
        """Test parsing JSON wrapped in markdown code block."""
        provider = ClaudeProvider(api_key="test")
        response = '''```json
{
    "title": "Code Block Grant",
    "confidence": 0.9
}
```'''

        result = provider._parse_response(response)
        assert result.title == "Code Block Grant"

    def test_parse_response_invalid_json(self):
        """Test parsing invalid JSON returns empty data."""
        provider = ClaudeProvider(api_key="test")
        response = "This is not JSON"

        result = provider._parse_response(response)
        assert result.confidence == 0.0
        assert result.title is None


class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    def test_is_available_without_key(self):
        """Test availability check without API key."""
        with patch.dict("os.environ", {}, clear=True):
            provider = OpenAIProvider(api_key=None)
            provider.api_key = None
            assert provider.is_available() is False

    def test_is_available_with_key(self):
        """Test availability check with API key."""
        provider = OpenAIProvider(api_key="sk-test-key")
        assert provider.is_available() is True

    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        provider = OpenAIProvider(api_key="test")
        response = '''{
            "title": "OpenAI Test Grant",
            "funding_total": 10000000,
            "categories": ["environment", "research"],
            "confidence": 0.95
        }'''

        result = provider._parse_response(response)
        assert result.title == "OpenAI Test Grant"
        assert result.funding_total == 10000000
        assert "environment" in result.categories


class TestLLMExtractor:
    """Tests for main LLMExtractor class."""

    def test_no_providers_available(self):
        """Test when no providers are available."""
        with patch.dict("os.environ", {}, clear=True):
            extractor = LLMExtractor()
            # Force no providers
            extractor.providers["claude"].api_key = None
            extractor.providers["openai"].api_key = None

            assert extractor.is_available() is False
            assert extractor.get_provider() is None

    def test_claude_preferred_when_both_available(self):
        """Test Claude is preferred when both providers available."""
        extractor = LLMExtractor(
            anthropic_api_key="claude-key",
            openai_api_key="openai-key",
        )

        provider = extractor.get_provider()
        assert isinstance(provider, ClaudeProvider)

    def test_forced_provider(self):
        """Test forcing specific provider."""
        extractor = LLMExtractor(
            provider="openai",
            anthropic_api_key="claude-key",
            openai_api_key="openai-key",
        )

        provider = extractor.get_provider()
        assert isinstance(provider, OpenAIProvider)

    def test_fallback_to_openai(self):
        """Test fallback to OpenAI when Claude unavailable."""
        extractor = LLMExtractor(
            anthropic_api_key=None,
            openai_api_key="openai-key",
        )
        # Ensure Claude is unavailable
        extractor.providers["claude"].api_key = None

        provider = extractor.get_provider()
        assert isinstance(provider, OpenAIProvider)

    @pytest.mark.asyncio
    async def test_extract_no_provider(self):
        """Test extraction returns empty when no provider."""
        extractor = LLMExtractor()
        extractor.providers["claude"].api_key = None
        extractor.providers["openai"].api_key = None

        result = await extractor.extract("Test content")
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_enhance_grant_fills_missing(self):
        """Test enhance_grant fills missing fields."""
        extractor = LLMExtractor(anthropic_api_key="test-key")

        # Mock the extract method
        mock_data = ExtractedGrantData(
            title="LLM Title",
            summary="LLM Summary",
            deadline=datetime(2024, 12, 31),
            funding_min=100000,
            funding_max=500000,
            confidence=0.9,
        )
        extractor.extract = AsyncMock(return_value=mock_data)

        # Existing grant with some fields
        grant = {
            "title": "Original Title",  # Should NOT be overwritten
            "summary": None,  # Should be filled
        }

        result = await extractor.enhance_grant(grant, "content")

        assert result["title"] == "Original Title"  # Preserved
        assert result["summary"] == "LLM Summary"  # Filled by LLM
        assert result["_llm_enhanced"] is True
        assert result["fundingAmount"]["min"] == 100000

    @pytest.mark.asyncio
    async def test_enhance_grant_low_confidence(self):
        """Test enhance_grant skips low confidence."""
        extractor = LLMExtractor(anthropic_api_key="test-key")

        mock_data = ExtractedGrantData(
            title="Low Confidence",
            confidence=0.3,  # Below 0.5 threshold
        )
        extractor.extract = AsyncMock(return_value=mock_data)

        grant = {"title": "Original"}
        result = await extractor.enhance_grant(grant, "content")

        # Should not be enhanced
        assert "_llm_enhanced" not in result


class TestExtractionPrompt:
    """Tests for extraction prompt."""

    def test_prompt_contains_required_fields(self):
        """Test prompt asks for all required fields."""
        required_fields = [
            "title",
            "summary",
            "description",
            "deadline",
            "funding_min",
            "funding_max",
            "eligibility",
            "contact_email",
        ]

        for field in required_fields:
            assert field in EXTRACTION_PROMPT

    def test_prompt_format_placeholder(self):
        """Test prompt has content placeholder."""
        assert "{content}" in EXTRACTION_PROMPT

    def test_prompt_is_czech(self):
        """Test prompt contains Czech instructions."""
        assert "Analyzuj" in EXTRACTION_PROMPT
        assert "částky" in EXTRACTION_PROMPT
