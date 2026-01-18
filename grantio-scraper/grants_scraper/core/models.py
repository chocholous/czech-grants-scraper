"""
Data models for the grants scraper.

Implements PRD-2 schema with type hints and validation.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class GrantType(str, Enum):
    """Type of grant opportunity."""
    CALL = "call"  # Time-limited call with deadline
    ONGOING_PROGRAM = "ongoing_program"  # Continuous program
    GRANT_SCHEME = "grant_scheme"  # Framework scheme


class GrantStatus(str, Enum):
    """Extraction status for the grant."""
    OK = "ok"  # All required fields extracted
    PARTIAL = "partial"  # Some fields missing
    ERROR = "error"  # Extraction failed


@dataclass
class FundingAmount:
    """Funding amount information."""
    min: Optional[int] = None
    max: Optional[int] = None
    total: Optional[int] = None
    currency: str = "CZK"

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Document:
    """Represents a downloadable document (PDF, XLSX, DOCX, etc.)."""

    title: str
    url: str
    doc_type: str  # call_text, guidelines, template, budget, annex, faq, etc.
    file_format: str  # pdf, xlsx, docx, zip

    size: Optional[str] = None
    validity_date: Optional[str] = None

    # After processing
    local_path: Optional[str] = None
    markdown_path: Optional[str] = None
    markdown_content: Optional[str] = None
    conversion_method: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class GrantTarget:
    """
    Target for scraping - represents a discovered grant URL.

    Used by navigators to pass discovery results to parsers.
    """
    url: str
    title: Optional[str] = None
    source_id: str = ""

    # Optional metadata from discovery phase
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Grant:
    """
    Full grant data following PRD-2 schema.

    This is the primary output of the scraping pipeline.
    """

    # Required identifiers
    source_id: str  # e.g., "mzd_gov", "dotaceeu", "mze_szif"
    source_name: str  # Human-readable source name
    source_url: str  # URL of the source website
    grant_url: str  # Direct URL to this grant

    # Core content
    title: str
    description: Optional[str] = None
    summary: Optional[str] = None

    # Funding
    funding_amount: Optional[FundingAmount] = None

    # Dates
    deadline: Optional[datetime] = None
    application_start: Optional[datetime] = None
    application_end: Optional[datetime] = None

    # Classification
    grant_type: GrantType = GrantType.CALL
    status: GrantStatus = GrantStatus.OK
    status_notes: str = ""

    # Eligibility
    eligibility: list[str] = field(default_factory=list)
    eligible_recipients: Optional[list[str]] = None

    # Contact
    contact_email: list[str] = field(default_factory=list)
    contact_phone: list[str] = field(default_factory=list)

    # Geographic
    regions: list[str] = field(default_factory=list)

    # Categories/tags
    categories: list[str] = field(default_factory=list)

    # Documents
    documents: list[Document] = field(default_factory=list)
    attachments: list[dict] = field(default_factory=list)

    # Application
    application_url: Optional[str] = None

    # Language
    language: str = "cs"

    # Metadata
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: Optional[str] = None

    # Additional source-specific metadata
    additional_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {}
        for k, v in asdict(self).items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
            elif isinstance(v, Enum):
                data[k] = v.value
            elif v is not None:
                data[k] = v
        return data

    def to_prd_schema(self) -> dict:
        """Convert to PRD-compatible schema for sync."""
        return {
            "recordType": "grant",
            "sourceId": self.source_id,
            "sourceName": self.source_name,
            "sourceUrl": self.source_url,
            "grantUrl": self.grant_url,
            "title": self.title,
            "summary": self.summary,
            "description": self.description,
            "eligibility": self.eligibility,
            "fundingAmount": self.funding_amount.to_dict() if self.funding_amount else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status.value,
            "statusNotes": self.status_notes,
            "extractedAt": self.extracted_at.isoformat(),
            "contentHash": self.content_hash,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "regions": self.regions,
            "categories": self.categories,
            "attachments": self.attachments,
            "documents": [d.to_dict() for d in self.documents],
            "language": self.language,
            "grantType": self.grant_type.value,
            "applicationUrl": self.application_url,
            **self.additional_metadata,
        }
