"""
LLM-based extraction plugin for intelligent grant data parsing.

Supports multiple providers:
- Anthropic Claude (recommended for Czech text)
- OpenAI GPT-4

This plugin is optional - requires API keys to function.
"""

import os
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ExtractedGrantData:
    """Structured data extracted by LLM."""
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    deadline_raw: Optional[str] = None
    funding_min: Optional[int] = None
    funding_max: Optional[int] = None
    funding_total: Optional[int] = None
    currency: str = "CZK"
    eligibility: list[str] = field(default_factory=list)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    application_url: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    raw_response: Optional[dict] = None


EXTRACTION_PROMPT = """Analyzuj následující text výzvy/dotačního programu a extrahuj strukturovaná data.

TEXT:
{content}

Extrahuj následující informace v JSON formátu:
{{
    "title": "Název výzvy/programu",
    "summary": "Krátké shrnutí (max 2 věty)",
    "description": "Podrobnější popis (max 500 znaků)",
    "deadline": "Datum uzávěrky ve formátu YYYY-MM-DD (pokud existuje)",
    "deadline_raw": "Originální text deadline (např. '31. 12. 2024 do 12:00')",
    "funding_min": číslo minimální částky v Kč (bez mezer, null pokud neznámé),
    "funding_max": číslo maximální částky v Kč (bez mezer, null pokud neznámé),
    "funding_total": číslo celkové alokace v Kč (bez mezer, null pokud neznámé),
    "eligibility": ["seznam oprávněných žadatelů"],
    "contact_email": "kontaktní email pokud je uveden",
    "contact_phone": "kontaktní telefon pokud je uveden",
    "application_url": "URL pro podání žádosti pokud je uvedeno",
    "categories": ["kategorie dotace - např. životní prostředí, vzdělávání"],
    "regions": ["regiony kde platí - např. Celá ČR, Moravskoslezský kraj"],
    "confidence": číslo 0-1 udávající důvěru v extrakci
}}

DŮLEŽITÉ:
- Pokud informace není v textu, použij null
- Částky převeď na celá čísla (např. "1,5 mil. Kč" = 1500000)
- Datum převeď na ISO formát YYYY-MM-DD
- Odpověz POUZE validním JSON bez dalšího textu
"""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def extract(self, content: str) -> ExtractedGrantData:
        """Extract structured data from content using LLM."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider for LLM extraction."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None

    def is_available(self) -> bool:
        """Check if Anthropic API key is configured."""
        return bool(self.api_key)

    def _get_client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("anthropic_not_installed", hint="pip install anthropic")
                raise
        return self._client

    async def extract(self, content: str) -> ExtractedGrantData:
        """Extract data using Claude."""
        if not self.is_available():
            logger.warning("claude_not_available", reason="No API key")
            return ExtractedGrantData(confidence=0.0)

        try:
            client = self._get_client()

            # Truncate content if too long (Claude has context limits)
            max_chars = 50000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n...[zkráceno]..."

            prompt = EXTRACTION_PROMPT.format(content=content)

            message = client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text
            return self._parse_response(response_text)

        except Exception as e:
            logger.error("claude_extraction_failed", error=str(e))
            return ExtractedGrantData(confidence=0.0)

    def _parse_response(self, response_text: str) -> ExtractedGrantData:
        """Parse Claude's JSON response into ExtractedGrantData."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to parse as direct JSON
                json_str = response_text.strip()

            data = json.loads(json_str)

            # Parse deadline if present
            deadline = None
            if data.get("deadline"):
                try:
                    deadline = datetime.strptime(data["deadline"], "%Y-%m-%d")
                except ValueError:
                    pass

            return ExtractedGrantData(
                title=data.get("title"),
                summary=data.get("summary"),
                description=data.get("description"),
                deadline=deadline,
                deadline_raw=data.get("deadline_raw"),
                funding_min=data.get("funding_min"),
                funding_max=data.get("funding_max"),
                funding_total=data.get("funding_total"),
                currency=data.get("currency", "CZK"),
                eligibility=data.get("eligibility", []),
                contact_email=data.get("contact_email"),
                contact_phone=data.get("contact_phone"),
                application_url=data.get("application_url"),
                categories=data.get("categories", []),
                regions=data.get("regions", []),
                confidence=data.get("confidence", 0.8),
                raw_response=data,
            )

        except json.JSONDecodeError as e:
            logger.error("json_parse_failed", error=str(e), response=response_text[:500])
            return ExtractedGrantData(confidence=0.0)


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider for LLM extraction."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None

    def is_available(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.api_key)

    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("openai_not_installed", hint="pip install openai")
                raise
        return self._client

    async def extract(self, content: str) -> ExtractedGrantData:
        """Extract data using GPT-4."""
        if not self.is_available():
            logger.warning("openai_not_available", reason="No API key")
            return ExtractedGrantData(confidence=0.0)

        try:
            client = self._get_client()

            # Truncate content if too long
            max_chars = 50000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n...[zkráceno]..."

            prompt = EXTRACTION_PROMPT.format(content=content)

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2048,
                response_format={"type": "json_object"},
            )

            response_text = response.choices[0].message.content
            return self._parse_response(response_text)

        except Exception as e:
            logger.error("openai_extraction_failed", error=str(e))
            return ExtractedGrantData(confidence=0.0)

    def _parse_response(self, response_text: str) -> ExtractedGrantData:
        """Parse OpenAI's JSON response into ExtractedGrantData."""
        try:
            data = json.loads(response_text)

            # Parse deadline if present
            deadline = None
            if data.get("deadline"):
                try:
                    deadline = datetime.strptime(data["deadline"], "%Y-%m-%d")
                except ValueError:
                    pass

            return ExtractedGrantData(
                title=data.get("title"),
                summary=data.get("summary"),
                description=data.get("description"),
                deadline=deadline,
                deadline_raw=data.get("deadline_raw"),
                funding_min=data.get("funding_min"),
                funding_max=data.get("funding_max"),
                funding_total=data.get("funding_total"),
                currency=data.get("currency", "CZK"),
                eligibility=data.get("eligibility", []),
                contact_email=data.get("contact_email"),
                contact_phone=data.get("contact_phone"),
                application_url=data.get("application_url"),
                categories=data.get("categories", []),
                regions=data.get("regions", []),
                confidence=data.get("confidence", 0.8),
                raw_response=data,
            )

        except json.JSONDecodeError as e:
            logger.error("json_parse_failed", error=str(e), response=response_text[:500])
            return ExtractedGrantData(confidence=0.0)


class LLMExtractor:
    """
    Main LLM extraction interface.

    Automatically selects available provider with preference order:
    1. Claude (better for Czech language)
    2. OpenAI GPT-4

    Usage:
        extractor = LLMExtractor()
        if extractor.is_available():
            data = await extractor.extract(page_content)
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        """
        Initialize LLM extractor.

        Args:
            provider: Force specific provider ('claude', 'openai') or None for auto
            anthropic_api_key: Override env ANTHROPIC_API_KEY
            openai_api_key: Override env OPENAI_API_KEY
        """
        self.providers: dict[str, LLMProvider] = {
            "claude": ClaudeProvider(api_key=anthropic_api_key),
            "openai": OpenAIProvider(api_key=openai_api_key),
        }
        self.forced_provider = provider
        self._selected_provider: Optional[LLMProvider] = None

    def is_available(self) -> bool:
        """Check if any LLM provider is available."""
        return any(p.is_available() for p in self.providers.values())

    def get_provider(self) -> Optional[LLMProvider]:
        """Get the selected/available provider."""
        if self._selected_provider:
            return self._selected_provider

        if self.forced_provider:
            provider = self.providers.get(self.forced_provider)
            if provider and provider.is_available():
                self._selected_provider = provider
                return provider
            logger.warning(
                "forced_provider_not_available",
                provider=self.forced_provider,
            )

        # Auto-select: prefer Claude for Czech
        for name in ["claude", "openai"]:
            provider = self.providers[name]
            if provider.is_available():
                self._selected_provider = provider
                logger.info("llm_provider_selected", provider=name)
                return provider

        return None

    async def extract(self, content: str) -> ExtractedGrantData:
        """
        Extract structured grant data from text content.

        Args:
            content: Raw text content from grant page

        Returns:
            ExtractedGrantData with parsed fields
        """
        provider = self.get_provider()
        if not provider:
            logger.warning("no_llm_provider_available")
            return ExtractedGrantData(confidence=0.0)

        return await provider.extract(content)

    async def enhance_grant(
        self,
        grant_dict: dict[str, Any],
        page_content: str,
    ) -> dict[str, Any]:
        """
        Enhance existing grant data with LLM extraction.

        Only fills in missing fields, doesn't overwrite existing data.

        Args:
            grant_dict: Existing grant data dictionary
            page_content: Raw text content for LLM analysis

        Returns:
            Enhanced grant dictionary
        """
        extracted = await self.extract(page_content)

        if extracted.confidence < 0.5:
            logger.warning(
                "low_confidence_extraction",
                confidence=extracted.confidence,
            )
            return grant_dict

        # Enhance missing fields only
        enhancements = {
            "title": extracted.title,
            "summary": extracted.summary,
            "description": extracted.description,
            "deadline": extracted.deadline.isoformat() if extracted.deadline else None,
            "eligibility": extracted.eligibility,
            "contact_email": extracted.contact_email,
            "contact_phone": extracted.contact_phone,
            "application_url": extracted.application_url,
            "categories": extracted.categories,
            "regions": extracted.regions,
        }

        # Handle funding amounts specially
        if extracted.funding_min or extracted.funding_max or extracted.funding_total:
            if not grant_dict.get("fundingAmount"):
                grant_dict["fundingAmount"] = {}

            if extracted.funding_min and not grant_dict["fundingAmount"].get("min"):
                grant_dict["fundingAmount"]["min"] = extracted.funding_min
            if extracted.funding_max and not grant_dict["fundingAmount"].get("max"):
                grant_dict["fundingAmount"]["max"] = extracted.funding_max
            if extracted.funding_total and not grant_dict["fundingAmount"].get("total"):
                grant_dict["fundingAmount"]["total"] = extracted.funding_total
            if not grant_dict["fundingAmount"].get("currency"):
                grant_dict["fundingAmount"]["currency"] = extracted.currency

        # Apply enhancements for missing fields
        for field, value in enhancements.items():
            if value and not grant_dict.get(field):
                grant_dict[field] = value
                logger.debug("field_enhanced", field=field, source="llm")

        # Add LLM metadata
        grant_dict["_llm_enhanced"] = True
        grant_dict["_llm_confidence"] = extracted.confidence

        return grant_dict


# Convenience function for quick extraction
async def extract_with_llm(content: str) -> ExtractedGrantData:
    """
    Quick extraction using default LLM provider.

    Args:
        content: Text content to analyze

    Returns:
        ExtractedGrantData with parsed fields
    """
    extractor = LLMExtractor()
    return await extractor.extract(content)
