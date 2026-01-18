"""
Normalization utilities for Czech grant data.

Handles:
- Czech date formats (9. 1. 2026, 30.4.2026)
- Czech currency amounts (1,5 mil. Kč, 500 000 Kč)
- Text cleanup and normalization
"""

import re
from datetime import datetime
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


# Czech month names for text-based date parsing
CZECH_MONTHS = {
    "ledna": 1, "únor": 2, "února": 2, "března": 3, "březen": 3,
    "dubna": 4, "duben": 4, "května": 5, "květen": 5, "června": 6,
    "červen": 6, "července": 7, "červenec": 7, "srpna": 8, "srpen": 8,
    "září": 9, "října": 10, "říjen": 10, "listopadu": 11, "listopad": 11,
    "prosince": 12, "prosinec": 12,
}


def parse_czech_date(text: str) -> Optional[datetime]:
    """
    Parse Czech date format into datetime.

    Supported formats:
    - "9. 1. 2026" (day. month. year with spaces)
    - "30.4.2026" (day.month.year without spaces)
    - "9.1.2026" (day.month.year)
    - "1. ledna 2026" (day. month_name year)

    Args:
        text: String containing a Czech date

    Returns:
        datetime object or None if parsing fails
    """
    if not text:
        return None

    text = text.strip()

    # Pattern 1: day. month. year with optional spaces
    pattern1 = r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})"
    match = re.search(pattern1, text)
    if match:
        day, month, year = match.groups()
        try:
            return datetime(int(year), int(month), int(day))
        except ValueError as e:
            logger.warning("invalid_date", text=text, error=str(e))
            return None

    # Pattern 2: day. month_name year
    pattern2 = r"(\d{1,2})\.\s*(\w+)\s+(\d{4})"
    match = re.search(pattern2, text)
    if match:
        day, month_name, year = match.groups()
        month_name_lower = month_name.lower()
        if month_name_lower in CZECH_MONTHS:
            try:
                return datetime(int(year), CZECH_MONTHS[month_name_lower], int(day))
            except ValueError as e:
                logger.warning("invalid_date", text=text, error=str(e))
                return None

    return None


def parse_czech_amount(text: str) -> Optional[int]:
    """
    Parse Czech currency amount from text.

    Supported formats:
    - "1 000 000 Kč" -> 1000000
    - "1,5 mil. Kč" -> 1500000
    - "2,3 mld. Kč" -> 2300000000
    - "500000" -> 500000
    - "1.5 mil" -> 1500000

    Args:
        text: String containing a Czech currency amount

    Returns:
        Integer amount in CZK or None if parsing fails
    """
    if not text:
        return None

    # Clean up text but keep it for keyword detection
    original = text.strip()
    original = original.replace("\u00a0", " ")  # Non-breaking space
    original_lower = original.lower()

    # Handle billions (mld. / miliard)
    if "mld" in original_lower or "miliard" in original_lower:
        # Extract number before mld/miliard
        match = re.search(r"([\d\s,\.]+)\s*(?:mld|miliard)", original_lower)
        if match:
            num_str = match.group(1).replace(" ", "").replace(",", ".")
            try:
                return int(float(num_str) * 1_000_000_000)
            except (ValueError, OverflowError):
                return None
        return None

    # Handle millions (mil. / milion)
    if "mil" in original_lower:
        # Extract number before mil
        match = re.search(r"([\d\s,\.]+)\s*mil", original_lower)
        if match:
            num_str = match.group(1).replace(" ", "").replace(",", ".")
            try:
                return int(float(num_str) * 1_000_000)
            except (ValueError, OverflowError):
                return None
        return None

    # Handle thousands (tis. / tisíc)
    if "tis" in original_lower:
        match = re.search(r"([\d\s,\.]+)\s*tis", original_lower)
        if match:
            num_str = match.group(1).replace(" ", "").replace(",", ".")
            try:
                return int(float(num_str) * 1_000)
            except (ValueError, OverflowError):
                return None
        return None

    # Plain number - remove currency suffixes and extract digits
    cleaned = original.replace("Kc", "").replace("Kč", "").replace("CZK", "").strip()
    num_str = re.sub(r"[^\d]", "", cleaned)
    try:
        return int(num_str) if num_str else None
    except ValueError:
        return None


def extract_amount_by_keywords(text: str, keywords: list[str]) -> Optional[int]:
    """
    Extract amount from text near specified keywords.

    Searches for patterns like "keyword: 1 000 000 Kč" or "keyword 1,5 mil.".

    Args:
        text: Full text to search in
        keywords: Keywords to look for (e.g., ["minimální částka", "minimum"])

    Returns:
        Extracted amount or None
    """
    text_lower = text.lower()

    for keyword in keywords:
        # Pattern: keyword followed by optional characters and then amount
        pattern = rf"{re.escape(keyword)}[^0-9]*?([\d\s,\.]+\s*(?:mil\.?|mld\.?|tis\.?|Kc|Kč|CZK)?)"
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            amount = parse_czech_amount(match.group(1))
            if amount and amount > 0:
                return amount

    return None


def extract_funding_amounts(text: str) -> dict:
    """
    Extract funding amounts (min, max, total) from text.

    Args:
        text: Full text to search

    Returns:
        Dict with keys: min, max, total, currency
    """
    min_keywords = [
        "minimální částka", "minimalni castka", "minimum", "nejméně", "nejmene", "od částky"
    ]
    max_keywords = [
        "maximální částka", "maximalni castka", "maximum", "nejvýše", "nejvyse", "až do", "az do", "do částky"
    ]
    total_keywords = [
        "alokace", "rozpočet", "rozpocet", "celková alokace", "celkova alokace",
        "celkový rozpočet", "celkovy rozpocet"
    ]

    return {
        "min": extract_amount_by_keywords(text, min_keywords),
        "max": extract_amount_by_keywords(text, max_keywords),
        "total": extract_amount_by_keywords(text, total_keywords),
        "currency": "CZK",
    }


def normalize_title(title: str) -> str:
    """
    Normalize grant title for consistent display.

    - Removes extra whitespace
    - Strips leading/trailing whitespace
    - Normalizes Unicode characters

    Args:
        title: Raw title string

    Returns:
        Normalized title
    """
    if not title:
        return ""

    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", title)
    normalized = normalized.strip()

    return normalized


def cleanup_html_text(text: str) -> str:
    """
    Clean up text extracted from HTML.

    - Removes extra whitespace and newlines
    - Removes common HTML artifacts
    - Normalizes punctuation spacing

    Args:
        text: Raw text from HTML

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Remove common HTML artifacts
    cleaned = re.sub(r"&nbsp;", " ", text)
    cleaned = re.sub(r"&amp;", "&", cleaned)
    cleaned = re.sub(r"&lt;", "<", cleaned)
    cleaned = re.sub(r"&gt;", ">", cleaned)

    # Normalize whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n", "\n\n", cleaned)
    cleaned = cleaned.strip()

    # Fix spacing around punctuation
    cleaned = re.sub(r"\s+([,\.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([,\.;:!?])(?=[^\s\d])", r"\1 ", cleaned)

    return cleaned


def extract_email(text: str) -> Optional[str]:
    """
    Extract email address from text.

    Args:
        text: Text to search

    Returns:
        First found email or None
    """
    if not text:
        return None

    pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
    match = re.search(pattern, text)
    return match.group(0) if match else None


def extract_phone(text: str) -> Optional[str]:
    """
    Extract Czech phone number from text.

    Args:
        text: Text to search

    Returns:
        First found phone number or None
    """
    if not text:
        return None

    # Czech phone patterns
    patterns = [
        r"\+420\s*\d{3}\s*\d{3}\s*\d{3}",  # +420 123 456 789
        r"\d{3}\s*\d{3}\s*\d{3}",  # 123 456 789
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).replace(" ", "")

    return None
