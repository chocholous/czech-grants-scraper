"""
Optional plugins for extended functionality.

Plugins provide additional capabilities that are not part of the core:
- pdf: PDF parsing with pdfplumber
- excel: Excel parsing with openpyxl/pandas
- llm: LLM-based extraction (optional)
"""

from .llm import (
    LLMExtractor,
    ExtractedGrantData,
    ClaudeProvider,
    OpenAIProvider,
    extract_with_llm,
)

__all__ = [
    "LLMExtractor",
    "ExtractedGrantData",
    "ClaudeProvider",
    "OpenAIProvider",
    "extract_with_llm",
]
