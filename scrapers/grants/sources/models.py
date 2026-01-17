"""
Data models for sub-scraper content extraction.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from datetime import datetime, timezone


@dataclass
class Document:
    """Represents a downloadable document (PDF, XLSX, DOCX, etc.)"""

    title: str                      # Document title/name
    url: str                        # Download URL
    doc_type: str                   # call_text, guidelines, template, budget, etc.
    file_format: str                # pdf, xlsx, docx, zip
    size: Optional[str] = None      # File size (e.g., "165.03 kB")
    validity_date: Optional[str] = None  # "Platnost: 18. 12. 2025"

    # After processing
    local_path: Optional[str] = None     # Path after download
    markdown_path: Optional[str] = None  # Path to converted markdown
    markdown_content: Optional[str] = None  # Converted markdown text
    conversion_method: Optional[str] = None  # pdfplumber, pandas, mammoth

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class EligibilityCriterion:
    """A single eligibility criterion with details."""

    criterion: str  # The criterion text in Czech
    category: str   # 'applicant', 'project', 'financial', 'territorial', 'temporal'
    is_mandatory: bool = True

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EvaluationCriterion:
    """A single evaluation/scoring criterion."""

    criterion: str
    max_points: Optional[int] = None
    weight: Optional[float] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EnhancedGrantInfo:
    """
    Enhanced grant information extracted via LLM.

    Contains detailed criteria and requirements that are hard to extract
    with traditional regex/CSS approaches.
    """

    # Eligibility criteria (categorized)
    eligibility_criteria: List[EligibilityCriterion] = field(default_factory=list)

    # Evaluation/scoring criteria
    evaluation_criteria: List[EvaluationCriterion] = field(default_factory=list)

    # Activities
    supported_activities: List[str] = field(default_factory=list)
    unsupported_activities: List[str] = field(default_factory=list)

    # Project requirements
    min_project_duration_months: Optional[int] = None
    max_project_duration_months: Optional[int] = None
    territorial_restrictions: Optional[str] = None
    required_attachments: List[str] = field(default_factory=list)

    # Financial details
    aid_intensity_percent: Optional[float] = None
    own_contribution_required: Optional[bool] = None

    # Thematic categorization
    thematic_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        data = asdict(self)
        return data


@dataclass
class GrantContent:
    """Full grant content extracted from external source"""

    # Source information
    source_url: str
    scraper_name: str              # "OPSTCzScraper", "NRBCzScraper", etc.
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Core content
    description: Optional[str] = None          # Full grant description
    summary: Optional[str] = None              # Short perex/summary

    # Funding information
    funding_amounts: Optional[Dict] = None     # {"total": 215000000, "currency": "CZK"}

    # Documents
    documents: List[Document] = field(default_factory=list)

    # Application details
    application_url: Optional[str] = None      # Portal for submissions
    contact_email: Optional[str] = None

    # Recipients
    eligible_recipients: Optional[List[str]] = None

    # Additional metadata
    additional_metadata: Dict = field(default_factory=dict)

    # LLM-enhanced data (optional)
    enhanced_info: Optional[EnhancedGrantInfo] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['scraped_at'] = self.scraped_at.isoformat()
        return data
