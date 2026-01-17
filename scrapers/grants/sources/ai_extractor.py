"""
AI-powered data extraction using Claude Haiku API.

Uses Claude Haiku to extract structured grant information from unstructured text
(HTML pages or PDF documents). More robust than regex patterns.
"""

import os
from typing import Optional, Dict, List
import json

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# Configurable API settings
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
HAIKU_MODEL = os.getenv('HAIKU_MODEL', 'claude-3-5-haiku-20241022')


def extract_grant_details(text: str, grant_title: str) -> Dict:
    """
    Extract structured grant details from unstructured text using Claude Haiku.

    Args:
        text: Raw text content (from HTML or PDF)
        grant_title: Title of the grant (for context)

    Returns:
        Dictionary with extracted fields:
        - eligibility: List[str] - List of eligible applicants
        - funding_min: int - Minimum funding amount in CZK (0 if not found)
        - funding_max: int - Maximum funding amount in CZK (0 if not found)
        - deadline: str - Deadline in YYYY-MM-DD format (or None)
        - summary: str - Brief summary of the grant
    """
    if not ANTHROPIC_AVAILABLE:
        return _fallback_extraction(text)

    if not ANTHROPIC_API_KEY:
        return _fallback_extraction(text)

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        # Prepare extraction prompt
        prompt = f"""Analyzuj následující text dotační výzvy a extrahuj strukturovaná data.

Grant: {grant_title}

Text výzvy:
{text[:8000]}  # Limit to first 8000 chars to avoid token limits

Extrahuj následující informace a vrať je jako JSON:

1. **eligibility** (pole stringů): Kdo může žádat o dotaci? Seznam oprávněných žadatelů (např. "krajské úřady", "neziskové organizace", "obce"). Pokud není specifikováno, vrať prázdné pole.

2. **funding_min** (číslo): Minimální výše dotace v Kč. Pokud není uvedeno, vrať 0.

3. **funding_max** (číslo): Maximální výše dotace v Kč. Pokud není uvedeno nebo je to celková alokace programu, zkus odhadnout max na projekt. Pokud opravdu není, vrať 0.

4. **deadline** (string): Termín pro podání žádostí ve formátu YYYY-MM-DD. Hledej formulace jako "do 30. 9. 2025", "termín: 15.8.2025". Pokud není, vrať null.

5. **summary** (string): Stručné shrnutí účelu dotace v 1-2 větách (max 200 znaků).

DŮLEŽITÉ:
- Vrať validní JSON bez markdown bloků
- Pokud nějaká informace není v textu, použij příslušnou default hodnotu
- Funding částky převeď na celá čísla (bez mezer, teček)
- Deadline musí být přesný datum formát YYYY-MM-DD"""

        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse response
        result_text = response.content[0].text.strip()

        # Remove markdown code blocks if present
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
            result_text = result_text.strip()

        data = json.loads(result_text)

        # Validate and normalize
        return {
            'eligibility': data.get('eligibility', []) or [],
            'funding_min': int(data.get('funding_min', 0) or 0),
            'funding_max': int(data.get('funding_max', 0) or 0),
            'deadline': data.get('deadline'),
            'summary': data.get('summary', '')[:200] if data.get('summary') else None,
        }

    except Exception as e:
        # Log error and fallback
        print(f"AI extraction failed: {e}")
        return _fallback_extraction(text)


def _fallback_extraction(text: str) -> Dict:
    """
    Fallback extraction when AI is not available.
    Returns empty/default values.
    """
    return {
        'eligibility': [],
        'funding_min': 0,
        'funding_max': 0,
        'deadline': None,
        'summary': None,
    }


def is_ai_extraction_available() -> bool:
    """Check if AI extraction is available (API key configured)."""
    return ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY is not None
