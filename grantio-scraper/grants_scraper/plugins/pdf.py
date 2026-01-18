"""
PDF parsing plugin using pdfplumber.

Extracts text, tables, and metadata from PDF documents.
"""

import re
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

# Check if pdfplumber is available
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("pdfplumber_not_installed", hint="pip install pdfplumber")


def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    """
    Extract all text from PDF.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text or None if failed
    """
    if not PDFPLUMBER_AVAILABLE:
        logger.error("pdfplumber_not_available")
        return None

    if not Path(pdf_path).exists():
        logger.error("pdf_not_found", path=pdf_path)
        return None

    try:
        text_parts = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        full_text = "\n\n".join(text_parts)
        logger.info(
            "pdf_extracted",
            path=pdf_path,
            pages=len(text_parts),
            chars=len(full_text),
        )

        return full_text

    except Exception as e:
        logger.error("pdf_extraction_failed", path=pdf_path, error=str(e))
        return None


def extract_tables_from_pdf(pdf_path: str) -> list[list[list[str]]]:
    """
    Extract all tables from PDF.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of tables, where each table is a list of rows,
        and each row is a list of cell values
    """
    if not PDFPLUMBER_AVAILABLE:
        logger.error("pdfplumber_not_available")
        return []

    if not Path(pdf_path).exists():
        logger.error("pdf_not_found", path=pdf_path)
        return []

    try:
        all_tables = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        # Clean up cell values
                        cleaned_table = []
                        for row in table:
                            cleaned_row = [
                                str(cell).strip() if cell else ""
                                for cell in row
                            ]
                            cleaned_table.append(cleaned_row)
                        all_tables.append(cleaned_table)

        logger.info(
            "pdf_tables_extracted",
            path=pdf_path,
            tables=len(all_tables),
        )

        return all_tables

    except Exception as e:
        logger.error("pdf_table_extraction_failed", path=pdf_path, error=str(e))
        return []


def convert_pdf_to_markdown(pdf_path: str) -> Optional[str]:
    """
    Convert PDF to markdown format.

    Extracts text and formats tables as markdown.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Markdown string or None if failed
    """
    if not PDFPLUMBER_AVAILABLE:
        logger.error("pdfplumber_not_available")
        return None

    if not Path(pdf_path).exists():
        logger.error("pdf_not_found", path=pdf_path)
        return None

    try:
        md_parts = []
        filename = Path(pdf_path).name

        md_parts.append(f"# {filename}\n")

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                md_parts.append(f"\n## Stránka {page_num}\n")

                # Extract text
                page_text = page.extract_text()
                if page_text:
                    # Clean up text
                    cleaned = _cleanup_pdf_text(page_text)
                    md_parts.append(cleaned)

                # Extract tables
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        md_table = _table_to_markdown(table)
                        md_parts.append(f"\n{md_table}\n")

        markdown = "\n".join(md_parts)

        logger.info(
            "pdf_converted_to_markdown",
            path=pdf_path,
            chars=len(markdown),
        )

        return markdown

    except Exception as e:
        logger.error("pdf_conversion_failed", path=pdf_path, error=str(e))
        return None


def _cleanup_pdf_text(text: str) -> str:
    """Clean up extracted PDF text."""
    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Remove page numbers
    text = re.sub(r"\n\d+\n", "\n", text)
    # Remove excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _table_to_markdown(table: list[list]) -> str:
    """Convert table to markdown format."""
    if not table or not table[0]:
        return ""

    # Calculate column widths
    num_cols = max(len(row) for row in table)
    col_widths = [3] * num_cols

    for row in table:
        for i, cell in enumerate(row):
            if i < num_cols:
                cell_text = str(cell) if cell else ""
                col_widths[i] = max(col_widths[i], len(cell_text))

    # Build markdown table
    lines = []

    # Header row (first row)
    if table:
        header = table[0]
        header_cells = [
            (str(cell) if cell else "").ljust(col_widths[i])
            for i, cell in enumerate(header[:num_cols])
        ]
        # Pad if needed
        while len(header_cells) < num_cols:
            header_cells.append("".ljust(col_widths[len(header_cells)]))
        lines.append("| " + " | ".join(header_cells) + " |")

        # Separator
        separator = ["-" * w for w in col_widths]
        lines.append("| " + " | ".join(separator) + " |")

    # Data rows
    for row in table[1:]:
        cells = [
            (str(cell) if cell else "").ljust(col_widths[i])
            for i, cell in enumerate(row[:num_cols])
        ]
        while len(cells) < num_cols:
            cells.append("".ljust(col_widths[len(cells)]))
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def get_pdf_metadata(pdf_path: str) -> Optional[dict]:
    """
    Extract PDF metadata.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Metadata dict or None
    """
    if not PDFPLUMBER_AVAILABLE:
        return None

    if not Path(pdf_path).exists():
        return None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            return {
                "pages": len(pdf.pages),
                "metadata": pdf.metadata or {},
            }
    except Exception:
        return None
