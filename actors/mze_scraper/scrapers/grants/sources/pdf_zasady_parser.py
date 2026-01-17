"""
Enhanced PDF parser for MZe Zásady documents with multi-pass analysis.

Improvements:
- Skips table of contents (TOC)
- Multi-pass parsing: identify programs, then extract sections
- Structured amount and deadline parsing
- Handles sub-programs (e.g., 20.A -> 20.A.a, 20.A.b, 20.A.c)
"""

import subprocess
import re
import os
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime


class ZasadyPDFParser:
    """Enhanced parser for Zásady PDF documents"""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.text_content = None
        self.lines = []
        self.programs = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def extract_text(self) -> str:
        """Extract text from PDF using pdftotext"""
        if not os.path.exists(self.pdf_path):
            raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")

        try:
            result = subprocess.run(
                ['pdftotext', '-layout', self.pdf_path, '-'],
                capture_output=True,
                text=True,
                check=True
            )
            self.text_content = result.stdout
            self.lines = self.text_content.split('\n')
            return self.text_content
        except subprocess.CalledProcessError as e:
            raise Exception(f"pdftotext failed: {e.stderr}")
        except FileNotFoundError:
            raise Exception("pdftotext not found. Install poppler-utils")

    def parse_programs(self) -> Dict[str, Dict]:
        """
        Parse all programs using multi-pass approach:
        1. Find start of program section (skip TOC)
        2. Identify all program boundaries
        3. Extract sections within each program
        """
        if not self.lines:
            self.extract_text()

        # Pass 1: Find where actual programs start (skip TOC)
        start_idx = self._find_program_section_start()

        # Pass 2: Identify all program boundaries
        program_ranges = self._identify_program_ranges(start_idx)

        # Pass 3: Extract content for each program
        for program_id, (start, end) in program_ranges.items():
            self.programs[program_id] = self._extract_program_content(
                program_id, start, end
            )

        return self.programs

    def _find_program_section_start(self) -> int:
        """
        Find where the actual program content starts (after TOC).

        TOC has pattern: "1.D. Podpora včelařství....................14"
        Actual content: "1.D. Podpora včelařství" (no dots, followed by "1 Účel")
        """
        for i, line in enumerate(self.lines):
            # Skip lines that look like TOC (have dots before page number)
            if re.search(r'\.{3,}', line):
                continue

            # Check for first program WITHOUT dots
            if re.match(r'^1\.D\.\s+Podpora', line):
                # Verify it's not TOC by checking for "1 Účel" nearby
                for j in range(i, min(i + 10, len(self.lines))):
                    if re.match(r'^1\s+Účel', self.lines[j]):
                        self.logger.info(f"Found program section start at line {i}")
                        return i

        # Fallback: skip first 500 lines (TOC + general conditions)
        self.logger.warning("Could not find program section start, using fallback")
        return 500

    def _identify_program_ranges(self, start_idx: int) -> Dict[str, Tuple[int, int]]:
        """
        Identify line ranges for each program.

        Program header patterns:
        - "1.D. Podpora včelařství"
        - "18. Podpora činnosti potravinových bank"
        - "20.A. Zlepšení životních podmínek v chovu dojnic"

        Must be followed by "1 Účel" or similar numbered section within ~10 lines.
        """
        # Simpler pattern - just match the ID and capture rest of line
        program_pattern = re.compile(r'^(\d+(?:\.[A-Z])?(?:\.[a-z])?)\.\s+(.+)$')

        ranges = {}
        current_program = None
        current_start = None

        for i in range(start_idx, len(self.lines)):
            line = self.lines[i].strip()

            # Skip empty lines
            if not line:
                continue

            # Check if this line starts a new program
            match = program_pattern.match(line)
            if match:
                program_id = match.group(1)

                # Validate it's a real program by checking for numbered section nearby
                is_valid_program = False
                for j in range(i + 1, min(i + 15, len(self.lines))):
                    next_line = self.lines[j].strip()
                    # Look for "1 Účel", "2 Předmět", etc.
                    if re.match(r'^\d+\s+(Účel|Předmět|Žadatel|Dotace|Podmínky)', next_line):
                        is_valid_program = True
                        break

                if not is_valid_program:
                    continue

                # Save previous program range
                if current_program and current_start is not None:
                    ranges[current_program] = (current_start, i - 1)

                # Start new program
                current_program = program_id
                current_start = i

        # Save last program
        if current_program and current_start is not None:
            ranges[current_program] = (current_start, len(self.lines) - 1)

        return ranges

    def _extract_program_content(
        self,
        program_id: str,
        start_idx: int,
        end_idx: int
    ) -> Dict:
        """
        Extract all content for a single program.

        Returns:
            Dict with name, sections, deadline, amounts
        """
        program_lines = self.lines[start_idx:end_idx + 1]

        # Extract program name from first line
        first_line = program_lines[0]
        name_match = re.match(r'^[\d\.A-Za-z]+\.\s+(.+?)(?:\s{2,}|\n|$)', first_line)
        name = name_match.group(1).strip() if name_match else ""

        # Extract sections
        sections = self._extract_sections(program_lines)

        # Parse specific fields
        deadline = self._extract_deadline_from_sections(sections)
        amounts = self._extract_amounts_from_sections(sections)
        eligibility = self._extract_eligibility_from_sections(sections)

        return {
            'id': program_id,
            'name': name,
            'sections': sections,
            'deadline': deadline,
            'funding_amounts': amounts,
            'eligibility': eligibility,
        }

    def _extract_sections(self, program_lines: List[str]) -> Dict[str, str]:
        """
        Extract numbered sections within a program.

        Sections:
        1 Účel
        2 Předmět dotace
        3 Žadatel
        4 Dotace
        5 Podmínky poskytnutí dotace
        6 Termín podání žádosti o dotaci
        7 Přílohy k žádosti o dotaci
        8 Termín příjmu dokladů
        9 Doklady prokazující nárok na dotaci

        Special handling:
        - Programs with "Specifikace jednotlivých dotačních podprogramů" structure
        - Programs with "A) Žádost" / "B) Formulář" sections before numbered content
        """
        # Check if this program has "Specifikace" structure (e.g., 20.A, 8.F)
        start_line = 1  # Default: skip first line (program header)

        for i, line in enumerate(program_lines):
            # Look for "Specifikace jednotlivých dotačních podprogramů"
            if re.search(r'Specifikace jednotlivých dotačních podprogramů', line, re.IGNORECASE):
                start_line = i + 1
                break
            # Or look for first sub-program with standard structure
            # e.g., "20.A.a. Podpora napájení dojnic" followed by "1 Účel"
            if re.match(r'^[\d\.A-Za-z]+\.\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]', line):
                # Check if there's "1 Účel" within next 20 lines
                for j in range(i + 1, min(i + 20, len(program_lines))):
                    if re.match(r'^1\s+(Účel|Předmět)', program_lines[j]):
                        start_line = i
                        break

        section_pattern = re.compile(
            r'^(\d+)\s+(Účel|Předmět|Žadatel|Konečný příjemce|Dotace|Výše dotace|'
            r'Podmínky|Termín|Přílohy|Doklady)'
        )

        sections = {}
        current_section = None
        current_text = []

        for line in program_lines[start_line:]:
            # Check for new section
            match = section_pattern.match(line)
            if match:
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_text).strip()

                # Start new section
                section_name = match.group(2)
                current_section = section_name
                current_text = [line]
            elif current_section:
                # Accumulate text for current section
                current_text.append(line)

        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_text).strip()

        return sections

    def _extract_deadline_from_sections(self, sections: Dict[str, str]) -> Optional[Dict]:
        """
        Extract deadline from Termín section.

        Patterns:
        - "začíná 3. 1. 2026 a končí 15. 1. 2026"
        - "do 15. 11. 2026"
        - "od 1. 10. 2025 do 30. 6. 2026"
        """
        termín_text = sections.get('Termín', '')

        # Pattern 1: začíná ... končí
        pattern1 = re.compile(
            r'začíná\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4}).*?končí\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})',
            re.IGNORECASE
        )
        match1 = pattern1.search(termín_text)
        if match1:
            return {
                'start_date': self._normalize_date(match1.group(1)),
                'end_date': self._normalize_date(match1.group(2)),
            }

        # Pattern 2: od ... do
        pattern2 = re.compile(
            r'od\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4}).*?do\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})',
            re.IGNORECASE
        )
        match2 = pattern2.search(termín_text)
        if match2:
            return {
                'start_date': self._normalize_date(match2.group(1)),
                'end_date': self._normalize_date(match2.group(2)),
            }

        # Pattern 3: do ...
        pattern3 = re.compile(r'do\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})', re.IGNORECASE)
        match3 = pattern3.search(termín_text)
        if match3:
            return {
                'start_date': None,
                'end_date': self._normalize_date(match3.group(1)),
            }

        return None

    def _extract_amounts_from_sections(self, sections: Dict[str, str]) -> Optional[Dict]:
        """
        Extract funding amounts from Dotace/Výše dotace section.

        Patterns:
        - "do 20 000 Kč/t"
        - "do 3 000 000 Kč"
        - "93 000 Kč/ha"

        Returns:
            {"min": 0, "max": 3000000, "currency": "CZK", "unit": "t"}
        """
        dotace_text = sections.get('Dotace', '') or sections.get('Výše dotace', '')

        amounts = []

        # Pattern: "do X Kč" or "X Kč/jednotka"
        pattern = re.compile(r'(\d+[\s\d]*)\s*Kč(?:/([a-zA-Z]+))?')

        for match in pattern.finditer(dotace_text):
            amount_str = match.group(1).replace(' ', '').replace('\xa0', '')
            unit = match.group(2)

            try:
                amount = int(amount_str)
                amounts.append({
                    'amount': amount,
                    'unit': unit,
                })
            except ValueError:
                continue

        if not amounts:
            return None

        # Find max amount
        max_amount = max(a['amount'] for a in amounts)

        # Find unit (prefer without unit for max)
        unit = next((a['unit'] for a in amounts if a['amount'] == max_amount), None)

        return {
            'min': 0,
            'max': max_amount,
            'currency': 'CZK',
            'unit': unit,
        }

    def _extract_eligibility_from_sections(self, sections: Dict[str, str]) -> List[str]:
        """
        Extract eligible recipients from Žadatel section.

        Returns list of entity types that can apply.
        """
        žadatel_text = sections.get('Žadatel', '') or sections.get('Konečný příjemce', '')

        eligibility = []

        # Common patterns
        patterns = [
            r'Zemědělský podnikatel',
            r'FO nebo PO',
            r'obce',
            r'kraje',
            r'neziskov[éý] organizac[ei]',
            r'NGO',
            r'sdružení',
            r'UCHS',
            r'potravinov[éý] bank[ya]',
        ]

        for pattern in patterns:
            if re.search(pattern, žadatel_text, re.IGNORECASE):
                eligibility.append(pattern)

        return eligibility

    def _normalize_date(self, date_str: str) -> str:
        """
        Normalize Czech date format to YYYY-MM-DD.

        Input: "3. 1. 2026" or "15. 11. 2026"
        Output: "2026-01-03" or "2026-11-15"
        """
        # Remove extra spaces
        date_str = re.sub(r'\s+', ' ', date_str.strip())

        # Parse
        match = re.match(r'(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})', date_str)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            return f"{year:04d}-{month:02d}-{day:02d}"

        return date_str

    def get_program(self, program_id: str) -> Optional[Dict]:
        """Get parsed data for specific program"""
        if not self.programs:
            self.parse_programs()

        normalized_id = program_id.rstrip('.')
        return self.programs.get(normalized_id)


if __name__ == '__main__':
    # Test
    import sys

    pdf_path = 'data/zasady_2026.pdf'

    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)

    parser = ZasadyPDFParser(pdf_path)
    parser.extract_text()
    programs = parser.parse_programs()

    print(f"Parsed {len(programs)} programs\n")

    # Show first 3 programs with details
    for i, (prog_id, prog) in enumerate(list(programs.items())[:3]):
        print(f"\n{'='*60}")
        print(f"Program {prog_id}: {prog['name']}")
        print(f"{'='*60}")
        print(f"Sections: {list(prog['sections'].keys())}")

        if prog['deadline']:
            print(f"Deadline: {prog['deadline']}")

        if prog['funding_amounts']:
            print(f"Amounts: {prog['funding_amounts']}")

        if prog['eligibility']:
            print(f"Eligibility: {prog['eligibility']}")

        # Show first section content (truncated)
        if prog['sections']:
            first_section = list(prog['sections'].keys())[0]
            content = prog['sections'][first_section]
            print(f"\n{first_section}:")
            print(content[:200] + "..." if len(content) > 200 else content)
