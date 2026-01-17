"""
Mapper for converting GrantContent to PRD output schema.

Maps internal GrantContent model to the PRD-compliant grant record format
with all mandatory fields.
"""

import hashlib
from typing import Dict, List, Optional
from datetime import datetime, timezone

from .scrapers_lib.models import GrantContent


def map_to_prd_schema(
    content: GrantContent,
    source_id: str,
    source_name: str,
    grant_url: str,
) -> Dict:
    """
    Convert GrantContent to PRD output schema.

    Args:
        content: Extracted grant content
        source_id: Unique source identifier (e.g., "mz-grants")
        source_name: Human-readable source name (e.g., "Ministerstvo zdravotnictví")
        grant_url: URL to the grant detail page

    Returns:
        Dictionary with PRD-compliant grant record

    Mandatory fields (PRD spec):
        - recordType, sourceId, sourceName, sourceUrl, grantUrl
        - title, eligibility, fundingAmount, deadline
        - status, statusNotes, extractedAt, contentHash
    """
    # Extract title from metadata or use source URL
    title = content.additional_metadata.get('title', '')
    if not title:
        title = f"Grant from {source_name}"

    # Extract deadline from metadata
    deadline = content.additional_metadata.get('deadline')

    # Build funding amount dict
    funding_amount = content.funding_amounts or {}
    if not funding_amount:
        funding_amount = {'min': 0, 'max': 0, 'currency': 'CZK'}

    # Build eligibility list
    eligibility = content.eligible_recipients or []
    if not eligibility:
        eligibility = ['Není specifikováno']

    # Build attachments list
    attachments = []
    for doc in content.documents:
        attachments.append({
            'title': doc.title,
            'url': doc.url,
            'type': doc.file_format,
        })

    # Determine status
    missing_fields = []
    if not title:
        missing_fields.append('title')
    if not deadline:
        missing_fields.append('deadline')
    if not eligibility or eligibility == ['Není specifikováno']:
        missing_fields.append('eligibility')
    if not content.funding_amounts:
        missing_fields.append('fundingAmount')

    if missing_fields:
        status = 'partial'
        # Note: For MZ grants, eligibility and funding are in PDF attachments
        status_notes = f"Missing fields: {', '.join(missing_fields)}. Details available in PDF attachments (Výzva, Metodika)."
    else:
        status = 'ok'
        status_notes = 'All mandatory fields present'

    # Generate content hash for deduplication
    content_hash = generate_content_hash(title, grant_url, deadline or '')

    # Build contact arrays
    contact_email = [content.contact_email] if content.contact_email else []

    # Build PRD record
    record = {
        # Mandatory fields
        'recordType': 'grant',
        'sourceId': source_id,
        'sourceName': source_name,
        'sourceUrl': content.source_url,
        'grantUrl': grant_url,
        'title': title,
        'eligibility': eligibility,
        'fundingAmount': funding_amount,
        'deadline': deadline,
        'status': status,
        'statusNotes': status_notes,
        'extractedAt': datetime.now(timezone.utc).isoformat(),
        'contentHash': content_hash,

        # Optional fields
        'summary': content.summary,
        'description': content.description,
        'contact_email': contact_email,
        'contact_phone': [],
        'criteria': [],
        'conditions': [],
        'applicationWindow': {},
        'regions': [],
        'categories': [],
        'attachments': attachments,
        'language': 'cs',
    }

    return record


def generate_content_hash(title: str, url: str, deadline: str) -> str:
    """
    Generate SHA256 hash for deduplication.

    Args:
        title: Grant title
        url: Grant URL
        deadline: Deadline date (YYYY-MM-DD)

    Returns:
        SHA256 hash string
    """
    # Combine key fields for hashing
    content = f"{title}|{url}|{deadline}"
    hash_obj = hashlib.sha256(content.encode('utf-8'))
    return hash_obj.hexdigest()


def validate_prd_record(record: Dict) -> tuple[bool, List[str]]:
    """
    Validate PRD record has all mandatory fields.

    Args:
        record: PRD grant record dictionary

    Returns:
        Tuple of (is_valid, missing_fields)
    """
    mandatory_fields = [
        'recordType',
        'sourceId',
        'sourceName',
        'sourceUrl',
        'grantUrl',
        'title',
        'eligibility',
        'fundingAmount',
        'deadline',
        'status',
        'statusNotes',
        'extractedAt',
        'contentHash',
    ]

    missing = []
    for field in mandatory_fields:
        if field not in record or record[field] is None:
            missing.append(field)
        # Check for empty strings
        elif isinstance(record[field], str) and not record[field].strip():
            missing.append(field)
        # Check for empty lists
        elif isinstance(record[field], list) and len(record[field]) == 0:
            missing.append(field)

    is_valid = len(missing) == 0
    return is_valid, missing
