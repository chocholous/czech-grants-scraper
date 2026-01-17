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

    # Deduplication
    content_hash: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['scraped_at'] = self.scraped_at.isoformat()
        return data

# Define a mock Grant class to satisfy imports in older scrapers that might rely on it before full content extraction
@dataclass
class Grant:
    title: Optional[str] = None
    source: Optional[str] = None
    sourceName: Optional[str] = None
    grantUrl: Optional[str] = None
    deadline: Optional[str] = None
    description: Optional[str] = None
    eligibility: Optional[List[str]] = field(default_factory=list)
    fundingAmount: Optional[Dict] = None
    status: Optional[str] = None
    statusNotes: Optional[str] = None
    extractedAt: Optional[str] = None
    contentHash: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
