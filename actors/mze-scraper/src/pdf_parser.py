"""
PDF parser for MZe Zásady (grant rules) documents
Uses pdftotext for text extraction and regex for structured data parsing
"""

import subprocess
import re
import os
from typing import Dict, List, Optional
from pathlib import Path
import requests
from config import USER_AGENT, DATA_DIR


class ZasadyPDFParser:
    """Parser for Zásady PDF documents"""

    def __init__(self, pdf_path: Optional[str] = None):
        """
        Initialize parser

        Args:
            pdf_path: Path to PDF file. If None, will download from SZIF
        """
        self.pdf_path = pdf_path
        self.text_content = None
        self.programs = {}

    def download_zasady(self, year: int, output_path: str) -> str:
        """
        Download Zásady PDF for given year

        Args:
            year: Year of Zásady document
            output_path: Where to save the PDF

        Returns:
            Path to downloaded PDF
        """
        # URL pattern for Zásady - this is discovered from scraping
        # For 2026: https://szif.gov.cz/cs/CmDocument?rid=%2Fapa_anon%2Fcs%2Fdokumenty_ke_stazeni%2Fnarodni_dotace%2F1764583283457.pdf

        # This URL needs to be discovered from HTML scraping first
        # For now, using known URL pattern
        url = f"https://szif.gov.cz/cs/CmDocument?rid=%2Fapa_anon%2Fcs%2Fdokumenty_ke_stazeni%2Fnarodni_dotace%2F{year}.pdf"

        print(f"Downloading Zásady for year {year}...")
        response = requests.get(url, headers={'User-Agent': USER_AGENT}, stream=True)

        if response.status_code != 200:
            raise Exception(f"Failed to download PDF: HTTP {response.status_code}")

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"Downloaded to {output_path}")
        return output_path

    def extract_text(self) -> str:
        """
        Extract text from PDF using pdftotext

        Returns:
            Extracted text content
        """
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")

        print(f"Extracting text from {self.pdf_path}...")

        # Use pdftotext to extract text
        try:
            result = subprocess.run(
                ['pdftotext', '-layout', self.pdf_path, '-'],
                capture_output=True,
                text=True,
                check=True
            )
            self.text_content = result.stdout
            print(f"Extracted {len(self.text_content)} characters")
            return self.text_content
        except subprocess.CalledProcessError as e:
            raise Exception(f"pdftotext failed: {e.stderr}")
        except FileNotFoundError:
            raise Exception("pdftotext not found. Please install poppler-utils")

    def parse_programs(self) -> Dict[str, Dict]:
        """
        Parse all grant programs from extracted text

        Returns:
            Dict mapping program_id to program data
        """
        if not self.text_content:
            self.extract_text()

        programs = {}
        lines = self.text_content.split('\n')

        # Pattern to match program headers like "1.D. Podpora včelařství"
        program_header_pattern = re.compile(r'^(\d+\.[A-Z]?\.?[a-z]?\.?)\s+(.+)$')

        current_program = None
        current_section = None
        current_section_text = []

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Check for program header
            match = program_header_pattern.match(line)
            if match:
                # Save previous program if exists
                if current_program:
                    self._finalize_program_section(
                        programs, current_program, current_section, current_section_text
                    )

                # Start new program
                program_id = match.group(1).rstrip('.')
                program_name = match.group(2)

                current_program = program_id
                programs[program_id] = {
                    'id': program_id,
                    'name': program_name,
                    'sections': {}
                }
                current_section = None
                current_section_text = []
                continue

            # Check for section headers (numbered sections like "1 Účel")
            section_match = re.match(r'^(\d+)\s+(Účel|Předmět|Žadatel|Dotace|Podmínky|Termín|Přílohy|Doklady)', line)
            if section_match and current_program:
                # Save previous section
                if current_section:
                    self._finalize_program_section(
                        programs, current_program, current_section, current_section_text
                    )

                current_section = section_match.group(2)
                current_section_text = [line]
                continue

            # Accumulate text for current section
            if current_program and current_section:
                current_section_text.append(line)

        # Save last program/section
        if current_program and current_section:
            self._finalize_program_section(
                programs, current_program, current_section, current_section_text
            )

        self.programs = programs
        print(f"Parsed {len(programs)} programs")
        return programs

    def _finalize_program_section(
        self,
        programs: Dict,
        program_id: str,
        section_name: str,
        section_lines: List[str]
    ):
        """Helper to save a section to program dict"""
        if not section_lines:
            return

        section_text = '\n'.join(section_lines)
        programs[program_id]['sections'][section_name] = section_text

        # Extract specific fields
        if section_name == 'Termín':
            programs[program_id]['deadline'] = self._extract_deadline(section_text)
        elif section_name == 'Dotace':
            programs[program_id]['amounts'] = self._extract_amounts(section_text)

    def _extract_deadline(self, text: str) -> Optional[Dict[str, str]]:
        """
        Extract deadline dates from Termín section

        Args:
            text: Section text

        Returns:
            Dict with start_date, end_date
        """
        # Pattern: "začíná DD. MM. YYYY a končí DD. MM. YYYY"
        pattern = r'začíná\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4}).*?končí\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})'
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return {
                'start_date': match.group(1).replace(' ', ''),
                'end_date': match.group(2).replace(' ', '')
            }

        # Alternative pattern: "do DD. MM. YYYY"
        pattern2 = r'do\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})'
        match2 = re.search(pattern2, text)
        if match2:
            return {
                'start_date': None,
                'end_date': match2.group(1).replace(' ', '')
            }

        return None

    def _extract_amounts(self, text: str) -> List[str]:
        """
        Extract monetary amounts from Dotace section

        Args:
            text: Section text

        Returns:
            List of found amounts (strings with Kč)
        """
        # Pattern for amounts: "123 456 Kč" or "123456Kč" or "123 Kč/t"
        pattern = r'(\d+[\s\d]*\s*Kč(?:/[a-zA-Z]+)?)'
        matches = re.findall(pattern, text)
        return [m.strip() for m in matches]

    def get_program(self, program_id: str) -> Optional[Dict]:
        """
        Get parsed data for specific program

        Args:
            program_id: Program ID like "18" or "1.D"

        Returns:
            Program data dict or None
        """
        if not self.programs:
            self.parse_programs()

        # Normalize ID (remove trailing dots)
        normalized_id = program_id.rstrip('.')
        return self.programs.get(normalized_id)


if __name__ == '__main__':
    # Test the parser
    import sys

    pdf_path = 'data/zasady_2026.pdf'

    if not os.path.exists(pdf_path):
        print(f"PDF not found at {pdf_path}")
        print("Downloading...")
        parser = ZasadyPDFParser()
        parser.download_zasady(2026, pdf_path)
        parser.pdf_path = pdf_path
    else:
        parser = ZasadyPDFParser(pdf_path)

    # Extract and parse
    parser.extract_text()
    programs = parser.parse_programs()

    # Show sample
    print(f"\nFound {len(programs)} programs")
    print("\nSample programs:")
    for program_id in list(programs.keys())[:3]:
        prog = programs[program_id]
        print(f"\n{program_id}: {prog['name']}")
        print(f"  Sections: {list(prog['sections'].keys())}")
        if 'deadline' in prog:
            print(f"  Deadline: {prog['deadline']}")
        if 'amounts' in prog:
            print(f"  Amounts: {prog['amounts'][:3]}")
