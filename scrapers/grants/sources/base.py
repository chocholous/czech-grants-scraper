"""
Abstract base class for grant sub-scrapers.

Each operational program website (opst.cz, nrb.cz, etc.) has its own
scraper implementation that inherits from this base class.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging
from .models import GrantContent


class AbstractGrantSubScraper(ABC):
    """
    Base class for site-specific grant content extraction.

    Supports optional LLM enrichment to extract detailed criteria
    and requirements from unstructured text.
    """

    def __init__(
        self,
        enable_llm: bool = False,
        llm_model: str = "anthropic/claude-haiku-4.5",
    ):
        """
        Initialize the scraper.

        Args:
            enable_llm: Whether to use LLM for enhanced extraction of
                       eligibility criteria, evaluation criteria, etc.
            llm_model: OpenRouter model identifier for LLM extraction.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.enable_llm = enable_llm
        self.llm_model = llm_model
        self._llm_extractor = None

    def _get_llm_extractor(self):
        """Get or create LLM extractor (lazy initialization)."""
        if self._llm_extractor is None:
            from .llm_extractor import LLMExtractor
            self._llm_extractor = LLMExtractor(model_name=self.llm_model)
        return self._llm_extractor

    async def enrich_with_llm(
        self,
        content: GrantContent,
        page_text: str,
        use_llm: Optional[bool] = None,
    ) -> GrantContent:
        """
        Enrich GrantContent with LLM-extracted data.

        Call this after traditional extraction to add eligibility criteria,
        evaluation criteria, and other semantic information.

        Args:
            content: GrantContent from traditional scraping
            page_text: Clean text content from the page (no HTML tags)
            use_llm: Override instance-level enable_llm setting

        Returns:
            The same GrantContent, now with enhanced_info populated
        """
        should_use_llm = use_llm if use_llm is not None else self.enable_llm

        if not should_use_llm:
            return content

        try:
            from .llm_extractor import enrich_grant_content

            self.logger.info(f"Running LLM enrichment for {content.source_url}...")
            content = await enrich_grant_content(
                grant_content=content,
                html_content=page_text,
                extractor=self._get_llm_extractor(),
            )

            if content.enhanced_info:
                self.logger.info(
                    f"LLM enrichment complete: "
                    f"{len(content.enhanced_info.eligibility_criteria)} eligibility criteria, "
                    f"{len(content.enhanced_info.thematic_keywords)} keywords"
                )
        except Exception as e:
            self.logger.warning(f"LLM enrichment failed (continuing without): {e}")

        return content

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """
        Check if this scraper can handle the given URL.

        Args:
            url: Full URL to check (e.g., "https://opst.cz/dotace/101-vyzva/")

        Returns:
            True if this scraper handles this domain/pattern
        """
        pass

    @abstractmethod
    async def extract_content(
        self, url: str, grant_metadata: dict, use_llm: Optional[bool] = None
    ) -> Optional[GrantContent]:
        """
        Extract full grant content from source page.

        Args:
            url: Full URL to the grant detail page
            grant_metadata: Metadata from dotaceeu.cz (title, call_number, etc.)
            use_llm: Override instance-level LLM setting for this call

        Returns:
            GrantContent object with description, documents, funding amounts, etc.
            Returns None if extraction fails
        """
        pass

    @abstractmethod
    async def download_document(self, doc_url: str, save_path: str) -> bool:
        """
        Download document to local filesystem.

        Args:
            doc_url: Full URL to document
            save_path: Absolute path where file should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        pass

    def get_scraper_name(self) -> str:
        """Return human-readable scraper name (e.g., 'OPSTCzScraper')"""
        return self.__class__.__name__
