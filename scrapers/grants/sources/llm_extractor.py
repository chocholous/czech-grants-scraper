"""
LLM-based structured extraction for grant data.

Uses pydantic-ai with the Apify OpenRouter Actor for structured output extraction,
providing more robust parsing than regex/CSS selector approaches.
"""

import os
import logging
from typing import Optional
from pydantic import BaseModel, Field

from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


# ===== Pydantic Schemas for Structured Extraction =====


class FundingInfo(BaseModel):
    """Extracted funding/allocation information."""

    min_amount: Optional[int] = Field(
        None, description="Minimum funding amount in CZK (e.g., 50000 for '50 000 Kč')"
    )
    max_amount: Optional[int] = Field(
        None, description="Maximum funding amount in CZK"
    )
    total_allocation: Optional[int] = Field(
        None, description="Total allocation/budget in CZK (e.g., 215000000 for '215 mil. Kč')"
    )
    currency: str = Field(default="CZK", description="Currency code")
    co_financing_rate: Optional[float] = Field(
        None, description="Co-financing rate as decimal (e.g., 0.85 for 85%)"
    )


class ExtractedGrantData(BaseModel):
    """Structured grant data extracted by LLM."""

    # Core content
    summary: Optional[str] = Field(
        None, description="Brief 1-2 sentence summary of what the grant funds"
    )
    description: Optional[str] = Field(
        None, description="Detailed description of grant purpose and eligible activities"
    )

    # Funding
    funding: Optional[FundingInfo] = Field(None, description="Funding amounts and rates")

    # Eligibility
    eligible_recipients: list[str] = Field(
        default_factory=list,
        description="List of eligible applicant types (e.g., 'obce', 'kraje', 'podnikatelé')",
    )
    eligible_activities: list[str] = Field(
        default_factory=list,
        description="List of activities/projects that can be funded",
    )

    # Application
    application_url: Optional[str] = Field(
        None, description="URL to application portal or submission system"
    )
    contact_email: Optional[str] = Field(
        None, description="Contact email for inquiries"
    )

    # Dates (as strings - will be parsed separately)
    application_deadline: Optional[str] = Field(
        None, description="Application submission deadline"
    )
    project_deadline: Optional[str] = Field(
        None, description="Project completion deadline"
    )


class EligibilityCriterion(BaseModel):
    """A single eligibility criterion with details."""

    criterion: str = Field(description="The criterion text in Czech")
    category: str = Field(
        description="Category: 'applicant' (who), 'project' (what), 'financial' (funding rules), 'territorial' (where), 'temporal' (when)"
    )
    is_mandatory: bool = Field(
        default=True, description="Whether this criterion is mandatory or optional"
    )


class EvaluationCriterion(BaseModel):
    """A single evaluation/scoring criterion."""

    criterion: str = Field(description="What is being evaluated")
    max_points: Optional[int] = Field(None, description="Maximum points for this criterion")
    weight: Optional[float] = Field(None, description="Weight as decimal (e.g., 0.3 for 30%)")


class EnhancedGrantData(BaseModel):
    """
    Enhanced grant data with deep semantic extraction.

    This extracts detailed criteria and requirements that are typically
    buried in unstructured text and hard to parse with regex.
    """

    # ===== ELIGIBILITY CRITERIA =====
    eligibility_criteria: list[EligibilityCriterion] = Field(
        default_factory=list,
        description="Detailed eligibility criteria for applicants and projects",
    )

    # ===== EVALUATION CRITERIA =====
    evaluation_criteria: list[EvaluationCriterion] = Field(
        default_factory=list,
        description="How applications are scored/evaluated",
    )

    # ===== SUPPORTED ACTIVITIES =====
    supported_activities: list[str] = Field(
        default_factory=list,
        description="Specific activities/costs that CAN be funded (způsobilé výdaje)",
    )

    unsupported_activities: list[str] = Field(
        default_factory=list,
        description="Activities/costs explicitly NOT eligible (nezpůsobilé výdaje)",
    )

    # ===== PROJECT REQUIREMENTS =====
    min_project_duration_months: Optional[int] = Field(
        None, description="Minimum project duration in months"
    )
    max_project_duration_months: Optional[int] = Field(
        None, description="Maximum project duration in months"
    )

    territorial_restrictions: Optional[str] = Field(
        None, description="Geographic/territorial restrictions (e.g., 'Karlovarský kraj')"
    )

    # ===== APPLICATION REQUIREMENTS =====
    required_attachments: list[str] = Field(
        default_factory=list,
        description="Documents required with application (e.g., 'podnikatelský záměr', 'rozpočet')",
    )

    # ===== FINANCIAL DETAILS =====
    aid_intensity_percent: Optional[float] = Field(
        None, description="Support intensity as percentage (e.g., 85.0 for 85%)"
    )

    own_contribution_required: Optional[bool] = Field(
        None, description="Whether applicant must provide own contribution"
    )

    # ===== THEMATIC FOCUS =====
    thematic_keywords: list[str] = Field(
        default_factory=list,
        description="Key themes/topics (e.g., 'digitalizace', 'životní prostředí', 'inovace')",
    )


# ===== LLM Extractor =====


EXTRACTION_SYSTEM_PROMPT = """You are a grant data extraction assistant specializing in Czech government grants and EU funds.

Your task is to extract structured information from grant documentation HTML. The content is in Czech.

Key extraction rules:
1. FUNDING AMOUNTS: Parse Czech number formats carefully:
   - "215 mil. Kč" = 215000000
   - "50 000 000 Kč" = 50000000
   - "5,5 mil. Kč" = 5500000
   - Always convert to integer CZK amounts

2. ELIGIBLE RECIPIENTS: Extract the types of organizations that can apply, such as:
   - obce (municipalities)
   - kraje (regions)
   - podnikatelé (businesses)
   - neziskové organizace / NNO (NGOs)
   - výzkumné organizace (research organizations)
   - školy (schools)

3. URLs: Only extract actual URLs, not text descriptions like "Na tomto webovém odkazu"

4. Be precise - if information is not clearly stated, leave the field as null rather than guessing.

5. For summaries, focus on WHAT the grant funds, not administrative details."""


ENHANCED_EXTRACTION_PROMPT = """You are an expert grant analyst specializing in Czech government grants and EU structural funds.

Your task is to perform DEEP extraction of grant criteria and requirements from documentation. The content is in Czech.

Focus on extracting:

1. ELIGIBILITY CRITERIA (kritéria způsobilosti):
   - WHO can apply (applicant types, legal forms, size restrictions)
   - WHAT projects qualify (thematic focus, activities)
   - WHERE (territorial restrictions)
   - WHEN (timing requirements)
   - Categorize each criterion appropriately

2. EVALUATION CRITERIA (hodnotící kritéria):
   - How applications are scored
   - Point allocations
   - Weights if mentioned

3. SUPPORTED vs UNSUPPORTED ACTIVITIES:
   - způsobilé výdaje (eligible costs)
   - nezpůsobilé výdaje (ineligible costs)
   - Be specific about what's included/excluded

4. PROJECT REQUIREMENTS:
   - Duration limits
   - Geographic restrictions
   - Required documents/attachments

5. FINANCIAL RULES:
   - Aid intensity (míra podpory)
   - Co-financing requirements
   - De minimis rules if applicable

6. THEMATIC KEYWORDS:
   - Extract key themes for categorization
   - Use Czech terms

Be thorough - extract ALL criteria mentioned, even if they seem minor.
Keep criterion text in Czech as it appears in the source."""


class LLMExtractor:
    """
    LLM-based extractor for structured grant data.

    Uses pydantic-ai with Apify OpenRouter Actor for structured output extraction.

    Supports two extraction modes:
    - Basic: Core grant info (funding, recipients, dates)
    - Enhanced: Deep criteria extraction (eligibility, evaluation, requirements)
    """

    def __init__(
        self,
        model_name: str = "anthropic/claude-haiku-4.5",
        apify_token: Optional[str] = None,
    ):
        """
        Initialize the LLM extractor.

        Args:
            model_name: OpenRouter model identifier (e.g., 'anthropic/claude-sonnet-4.5')
            apify_token: Apify API token. If not provided, reads from APIFY_TOKEN env var.
        """
        self.model_name = model_name
        self.apify_token = apify_token or os.environ.get("APIFY_TOKEN")

        if not self.apify_token:
            raise ValueError(
                "APIFY_TOKEN environment variable not set. "
                "Required for Apify OpenRouter Actor."
            )

        # Create custom OpenAI client pointing to Apify OpenRouter Actor
        self._client = AsyncOpenAI(
            base_url="https://openrouter.apify.actor/api/v1",
            api_key="placeholder",  # Not used, but required by SDK
            default_headers={"Authorization": f"Bearer {self.apify_token}"},
        )

        # Create pydantic-ai model
        self._model = OpenAIModel(
            model_name,
            provider=OpenAIProvider(openai_client=self._client),
        )

        # Basic extraction agent
        self._basic_agent = Agent(
            self._model,
            output_type=ExtractedGrantData,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
        )

        # Enhanced extraction agent (deep criteria analysis)
        self._enhanced_agent = Agent(
            self._model,
            output_type=EnhancedGrantData,
            system_prompt=ENHANCED_EXTRACTION_PROMPT,
        )

        logger.info(f"LLMExtractor initialized with model: {model_name}")

    async def extract(
        self,
        html_content: str,
        page_url: str,
        existing_metadata: Optional[dict] = None,
    ) -> Optional[ExtractedGrantData]:
        """
        Extract structured grant data from HTML content.

        Args:
            html_content: Raw HTML or text content from grant page
            page_url: Source URL (for context)
            existing_metadata: Optional metadata already extracted (to avoid re-extraction)

        Returns:
            ExtractedGrantData or None if extraction fails
        """
        try:
            # Truncate very long content to avoid token limits
            max_chars = 30000
            if len(html_content) > max_chars:
                logger.warning(
                    f"Content truncated from {len(html_content)} to {max_chars} chars"
                )
                html_content = html_content[:max_chars]

            # Build prompt with context
            prompt = f"""Extract structured grant information from this Czech grant page.

Source URL: {page_url}

Page content:
---
{html_content}
---

Extract all available information into the structured format."""

            # Run extraction
            result = await self._basic_agent.run(prompt)

            logger.info(
                f"Extracted from {page_url}: "
                f"summary={len(result.output.summary or '')} chars, "
                f"recipients={len(result.output.eligible_recipients)}"
            )

            return result.output

        except Exception as e:
            logger.error(f"LLM extraction failed for {page_url}: {e}")
            return None

    async def extract_from_documents(
        self,
        document_texts: list[str],
        page_url: str,
    ) -> Optional[ExtractedGrantData]:
        """
        Extract grant data from converted document texts (PDFs, DOCX, etc.).

        Useful when the main page lacks details but attached documents have them.

        Args:
            document_texts: List of markdown-converted document contents
            page_url: Source URL for context

        Returns:
            ExtractedGrantData or None if extraction fails
        """
        if not document_texts:
            return None

        # Combine documents with separators
        combined = "\n\n---DOCUMENT BOUNDARY---\n\n".join(document_texts)

        return await self.extract(
            html_content=combined,
            page_url=page_url,
        )

    async def extract_enhanced(
        self,
        html_content: str,
        page_url: str,
    ) -> Optional[EnhancedGrantData]:
        """
        Extract enhanced grant data with deep criteria analysis.

        This performs thorough extraction of:
        - Eligibility criteria (categorized)
        - Evaluation/scoring criteria
        - Supported vs unsupported activities
        - Project requirements
        - Financial rules

        Args:
            html_content: Raw HTML or text content from grant page
            page_url: Source URL (for context)

        Returns:
            EnhancedGrantData or None if extraction fails
        """
        try:
            # Truncate very long content to avoid token limits
            max_chars = 50000  # Allow more for enhanced extraction
            if len(html_content) > max_chars:
                logger.warning(
                    f"Content truncated from {len(html_content)} to {max_chars} chars"
                )
                html_content = html_content[:max_chars]

            prompt = f"""Perform deep extraction of grant criteria and requirements.

Source URL: {page_url}

Grant documentation:
---
{html_content}
---

Extract ALL eligibility criteria, evaluation criteria, supported/unsupported activities,
project requirements, and financial rules. Be thorough."""

            result = await self._enhanced_agent.run(prompt)

            logger.info(
                f"Enhanced extraction from {page_url}: "
                f"eligibility={len(result.output.eligibility_criteria)}, "
                f"evaluation={len(result.output.evaluation_criteria)}, "
                f"supported={len(result.output.supported_activities)}"
            )

            return result.output

        except Exception as e:
            logger.error(f"Enhanced LLM extraction failed for {page_url}: {e}")
            return None

    async def extract_full(
        self,
        html_content: str,
        page_url: str,
    ) -> tuple[Optional[ExtractedGrantData], Optional[EnhancedGrantData]]:
        """
        Extract both basic and enhanced data in parallel.

        Args:
            html_content: Raw HTML or text content
            page_url: Source URL

        Returns:
            Tuple of (basic_data, enhanced_data)
        """
        import asyncio

        basic_task = self.extract(html_content, page_url)
        enhanced_task = self.extract_enhanced(html_content, page_url)

        basic, enhanced = await asyncio.gather(basic_task, enhanced_task)
        return basic, enhanced


# ===== Convenience functions =====


async def extract_grant_with_llm(
    html_content: str,
    page_url: str,
    model_name: str = "anthropic/claude-haiku-4.5",
) -> Optional[ExtractedGrantData]:
    """
    Convenience function for one-off extraction.

    For repeated use, instantiate LLMExtractor directly to reuse the client.
    """
    extractor = LLMExtractor(model_name=model_name)
    return await extractor.extract(html_content, page_url)


def enhanced_to_dataclass(enhanced: EnhancedGrantData):
    """
    Convert pydantic EnhancedGrantData to dataclass EnhancedGrantInfo.

    This bridges the pydantic models used by the LLM agent with the
    dataclass models used by the scraper infrastructure.
    """
    from .models import EnhancedGrantInfo, EligibilityCriterion, EvaluationCriterion

    return EnhancedGrantInfo(
        eligibility_criteria=[
            EligibilityCriterion(
                criterion=c.criterion,
                category=c.category,
                is_mandatory=c.is_mandatory,
            )
            for c in enhanced.eligibility_criteria
        ],
        evaluation_criteria=[
            EvaluationCriterion(
                criterion=c.criterion,
                max_points=c.max_points,
                weight=c.weight,
            )
            for c in enhanced.evaluation_criteria
        ],
        supported_activities=enhanced.supported_activities,
        unsupported_activities=enhanced.unsupported_activities,
        min_project_duration_months=enhanced.min_project_duration_months,
        max_project_duration_months=enhanced.max_project_duration_months,
        territorial_restrictions=enhanced.territorial_restrictions,
        required_attachments=enhanced.required_attachments,
        aid_intensity_percent=enhanced.aid_intensity_percent,
        own_contribution_required=enhanced.own_contribution_required,
        thematic_keywords=enhanced.thematic_keywords,
    )


async def enrich_grant_content(
    grant_content,  # GrantContent dataclass
    html_content: str,
    extractor: Optional[LLMExtractor] = None,
    model_name: str = "anthropic/claude-haiku-4.5",
):
    """
    Enrich a GrantContent object with LLM-extracted enhanced data.

    This is the main integration point for scrapers. Call this after
    traditional extraction to add eligibility criteria, evaluation criteria,
    and other semantic information.

    Args:
        grant_content: GrantContent dataclass from traditional scraping
        html_content: Raw HTML/text content from the grant page
        extractor: Optional pre-configured LLMExtractor (for reuse)
        model_name: Model to use if creating new extractor

    Returns:
        The same GrantContent object, now with enhanced_info populated
    """
    if extractor is None:
        extractor = LLMExtractor(model_name=model_name)

    enhanced = await extractor.extract_enhanced(
        html_content=html_content,
        page_url=grant_content.source_url,
    )

    if enhanced:
        grant_content.enhanced_info = enhanced_to_dataclass(enhanced)

        # Also fill in any missing basic fields from enhanced extraction
        if not grant_content.summary and enhanced.thematic_keywords:
            # Generate a basic summary from keywords if missing
            pass  # Could add LLM-based summary here

    return grant_content
