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


def parse_czech_date(text: str, include_time: bool = False) -> Optional[datetime]:
    """
    Parse Czech date format into datetime.

    Supported formats:
    - "9. 1. 2026" (day. month. year with spaces)
    - "30.4.2026" (day.month.year without spaces)
    - "9.1.2026" (day.month.year)
    - "1. ledna 2026" (day. month_name year)
    - "31. 12. 2024 12:00" (with time)
    - "2024-12-31" (ISO format)

    Args:
        text: String containing a Czech date
        include_time: Whether to try parsing time component

    Returns:
        datetime object or None if parsing fails
    """
    if not text:
        return None

    text = text.strip()

    # Pattern 0: ISO format YYYY-MM-DD
    iso_pattern = r"(\d{4})-(\d{2})-(\d{2})"
    match = re.search(iso_pattern, text)
    if match:
        year, month, day = match.groups()
        try:
            return datetime(int(year), int(month), int(day))
        except ValueError:
            pass

    # Pattern 1: day. month. year with optional spaces and optional time
    if include_time:
        pattern1_time = r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\s+(\d{1,2})[:\.](\d{2})"
        match = re.search(pattern1_time, text)
        if match:
            day, month, year, hour, minute = match.groups()
            try:
                return datetime(int(year), int(month), int(day), int(hour), int(minute))
            except ValueError as e:
                logger.warning("invalid_date_time", text=text, error=str(e))

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


def extract_deadline(text: str) -> Optional[datetime]:
    """
    Extract deadline date from text with keyword detection.

    Searches for Czech deadline keywords and extracts associated date.

    Supported keywords:
    - "uzávěrka", "uzaverka"
    - "do", "nejpozději do"
    - "deadline"
    - "termín podání", "termin podani"
    - "konec příjmu", "konec prijmu"
    - "platnost do"

    Args:
        text: Full text to search

    Returns:
        Deadline datetime or None
    """
    if not text:
        return None

    text_lower = text.lower()

    # Keywords indicating deadline
    deadline_keywords = [
        "uzávěrka",
        "uzaverka",
        "nejpozději do",
        "nejpozdeji do",
        "deadline",
        "termín podání",
        "termin podani",
        "konec příjmu",
        "konec prijmu",
        "platnost do",
        "příjem žádostí do",
        "prijem zadosti do",
        "lhůta pro podání",
        "lhuta pro podani",
    ]

    for keyword in deadline_keywords:
        # Find keyword position
        pos = text_lower.find(keyword)
        if pos == -1:
            continue

        # Extract text around keyword (200 chars after)
        context = text[pos:pos + 200]

        # Try to parse date from context
        date = parse_czech_date(context, include_time=True)
        if date:
            logger.debug("deadline_extracted", keyword=keyword, date=date.isoformat())
            return date

    # Fallback: look for any date pattern with "do" before it
    pattern = r"do\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})"
    match = re.search(pattern, text_lower)
    if match:
        date = parse_czech_date(match.group(1), include_time=False)
        if date:
            return date

    return None


def extract_all_dates(text: str) -> list[datetime]:
    """
    Extract all dates from text.

    Args:
        text: Text to search

    Returns:
        List of datetime objects found
    """
    if not text:
        return []

    dates = []

    # Find all Czech date patterns
    pattern = r"\d{1,2}\.\s*\d{1,2}\.\s*\d{4}"
    matches = re.findall(pattern, text)

    for match in matches:
        date = parse_czech_date(match)
        if date:
            dates.append(date)

    return dates


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


def extract_funding_range(text: str) -> tuple[Optional[int], Optional[int]]:
    """
    Extract funding range (min, max) from text patterns.

    Looks for patterns like:
    - "100 000 - 500 000 Kč"
    - "od 100 tis. do 5 mil. Kč"
    - "100 000 až 500 000 Kč"

    Args:
        text: Text to search

    Returns:
        Tuple of (min_amount, max_amount), either may be None
    """
    if not text:
        return None, None

    text = text.replace("\u00a0", " ")  # Non-breaking space

    # Pattern 1: X - Y Kč or X – Y Kč (with dash/en-dash)
    pattern1 = r"([\d\s,\.]+(?:\s*(?:mil|mld|tis)\.?)?)\s*[-–]\s*([\d\s,\.]+(?:\s*(?:mil|mld|tis)\.?)?)\s*(?:Kč|CZK|EUR)"
    match = re.search(pattern1, text, re.IGNORECASE)
    if match:
        min_str, max_str = match.groups()
        min_val = parse_czech_amount(min_str + " Kč")
        max_val = parse_czech_amount(max_str + " Kč")
        if min_val and max_val:
            return min_val, max_val

    # Pattern 2: od X do Y
    pattern2 = r"od\s+([\d\s,\.]+(?:\s*(?:mil|mld|tis)\.?)?(?:\s*Kč)?)\s+do\s+([\d\s,\.]+(?:\s*(?:mil|mld|tis)\.?)?(?:\s*Kč)?)"
    match = re.search(pattern2, text, re.IGNORECASE)
    if match:
        min_str, max_str = match.groups()
        min_val = parse_czech_amount(min_str if "Kč" in min_str else min_str + " Kč")
        max_val = parse_czech_amount(max_str if "Kč" in max_str else max_str + " Kč")
        if min_val or max_val:
            return min_val, max_val

    # Pattern 3: X až Y Kč
    pattern3 = r"([\d\s,\.]+(?:\s*(?:mil|mld|tis)\.?)?)\s+až\s+([\d\s,\.]+(?:\s*(?:mil|mld|tis)\.?)?)\s*(?:Kč|CZK|EUR)"
    match = re.search(pattern3, text, re.IGNORECASE)
    if match:
        min_str, max_str = match.groups()
        min_val = parse_czech_amount(min_str + " Kč")
        max_val = parse_czech_amount(max_str + " Kč")
        if min_val and max_val:
            return min_val, max_val

    return None, None


def detect_currency(text: str) -> str:
    """
    Detect currency from text.

    Args:
        text: Text to analyze

    Returns:
        Currency code: 'CZK', 'EUR', or 'CZK' as default
    """
    text_lower = text.lower()

    # Count occurrences
    eur_count = len(re.findall(r'\beur\b|€', text_lower))
    czk_count = len(re.findall(r'\bkč\b|\bczk\b|korun', text_lower))

    if eur_count > czk_count:
        return "EUR"
    return "CZK"


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

    Uses multiple strategies:
    1. Direct range extraction (X - Y Kč)
    2. Keyword-based extraction (minimální částka: X)
    3. Fallback patterns

    Args:
        text: Full text to search

    Returns:
        Dict with keys: min, max, total, currency
    """
    # First try to extract range directly
    range_min, range_max = extract_funding_range(text)

    min_keywords = [
        "minimální částka", "minimalni castka", "minimum", "nejméně", "nejmene",
        "od částky", "min. výše", "min. vyse", "minimální výše", "minimalni vyse"
    ]
    max_keywords = [
        "maximální částka", "maximalni castka", "maximum", "nejvýše", "nejvyse",
        "až do", "az do", "do částky", "max. výše", "max. vyse", "maximální výše"
    ]
    total_keywords = [
        "alokace", "rozpočet", "rozpocet", "celková alokace", "celkova alokace",
        "celkový rozpočet", "celkovy rozpocet", "celkem", "vyčleněno", "vyclene",
        "finanční prostředky", "financni prostredky"
    ]

    # Try keyword extraction
    keyword_min = extract_amount_by_keywords(text, min_keywords)
    keyword_max = extract_amount_by_keywords(text, max_keywords)
    keyword_total = extract_amount_by_keywords(text, total_keywords)

    # Prefer range extraction if both found, else use keywords
    final_min = range_min if range_min else keyword_min
    final_max = range_max if range_max else keyword_max

    # Detect currency
    currency = detect_currency(text)

    return {
        "min": final_min,
        "max": final_max,
        "total": keyword_total,
        "currency": currency,
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
