"""
Utility functions for validation and data processing.
"""

import hashlib
from typing import Dict, List
from datetime import datetime


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
        # Check for empty lists (but allow ['Není specifikováno'] for eligibility)
        elif isinstance(record[field], list) and len(record[field]) == 0:
            missing.append(field)

    is_valid = len(missing) == 0
    return is_valid, missing


def is_date_in_past(date_str: str) -> bool:
    """
    Check if a date string (YYYY-MM-DD) is in the past.

    Args:
        date_str: Date in ISO format (YYYY-MM-DD)

    Returns:
        True if date is in the past, False otherwise
    """
    if not date_str:
        return False

    try:
        date = datetime.fromisoformat(date_str)
        return date.date() < datetime.now().date()
    except (ValueError, TypeError):
        return False
