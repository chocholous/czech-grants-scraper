"""
Main scraper combining HTML and PDF data sources
"""

import json
import os
from datetime import datetime
from typing import Dict, List
from html_scraper import SZIFHTMLScraper
from pdf_parser import ZasadyPDFParser
from config import OUTPUT_DIR, DATA_DIR, CURRENT_YEAR


class MZeGrantsScraper:
    """Main scraper orchestrating HTML and PDF data extraction"""

    def __init__(self, year: int = CURRENT_YEAR):
        """
        Initialize scraper

        Args:
            year: Year to scrape data for
        """
        self.year = year
        self.html_scraper = SZIFHTMLScraper()
        self.pdf_parser = None
        self.combined_data = []

    def scrape_all(self) -> List[Dict]:
        """
        Scrape all grant programs combining HTML and PDF sources

        Returns:
            List of grant program dicts
        """
        print(f"=== MZe National Grants Scraper - Year {self.year} ===\n")

        # Step 1: Get program list from HTML
        print("Step 1: Fetching program list from HTML...")
        html_programs = self.html_scraper.get_program_list()
        print(f"Found {len(html_programs)} programs\n")

        # Step 2: Download and parse PDF Zásady
        print("Step 2: Processing PDF Zásady document...")
        pdf_path = os.path.join(DATA_DIR, f'zasady_{self.year}.pdf')

        # Use existing PDF if available, otherwise download
        if not os.path.exists(pdf_path):
            self.pdf_parser = ZasadyPDFParser()
            try:
                self.pdf_parser.download_zasady(self.year, pdf_path)
            except Exception as e:
                print(f"Warning: Could not download PDF: {e}")
                print("Trying to use existing file...")

        self.pdf_parser = ZasadyPDFParser(pdf_path)

        if os.path.exists(pdf_path):
            try:
                self.pdf_parser.extract_text()
                pdf_programs = self.pdf_parser.parse_programs()
                print(f"Parsed {len(pdf_programs)} programs from PDF\n")
            except Exception as e:
                print(f"Warning: Could not parse PDF: {e}")
                pdf_programs = {}
        else:
            print("Warning: PDF not available, using HTML data only\n")
            pdf_programs = {}

        # Step 3: Fetch detailed HTML for each program
        print("Step 3: Fetching program details from HTML...")
        for i, prog in enumerate(html_programs, 1):
            print(f"  [{i}/{len(html_programs)}] {prog['program_id']}...", end='')

            try:
                detail = self.html_scraper.get_program_detail(prog['program_url'])

                # Combine HTML and PDF data
                combined = {
                    'program_id': prog['program_id'],
                    'name': prog['name'],
                    'year': self.year,
                    'url': prog['program_url'],
                    'description': detail['description'],
                    'news': detail['news'],
                    'documents': detail['documents'],
                    'scraped_at': datetime.now().isoformat()
                }

                # Add PDF data if available
                pdf_data = pdf_programs.get(prog['program_id'])
                if pdf_data:
                    combined['pdf_data'] = {
                        'sections': pdf_data.get('sections', {}),
                        'deadline': pdf_data.get('deadline'),
                        'amounts': pdf_data.get('amounts')
                    }
                    print(" ✓ (with PDF)")
                else:
                    combined['pdf_data'] = None
                    print(" ✓ (HTML only)")

                self.combined_data.append(combined)

            except Exception as e:
                print(f" ✗ Error: {e}")
                continue

        print(f"\nSuccessfully scraped {len(self.combined_data)} programs")
        return self.combined_data

    def export_json(self, filename: str = None) -> str:
        """
        Export scraped data to JSON

        Args:
            filename: Output filename. If None, auto-generated

        Returns:
            Path to exported file
        """
        if not self.combined_data:
            raise ValueError("No data to export. Run scrape_all() first")

        # Create output directory
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'mze_grants_{self.year}_{timestamp}.json'

        output_path = os.path.join(OUTPUT_DIR, filename)

        # Export
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    'metadata': {
                        'year': self.year,
                        'scraped_at': datetime.now().isoformat(),
                        'total_programs': len(self.combined_data)
                    },
                    'programs': self.combined_data
                },
                f,
                ensure_ascii=False,
                indent=2
            )

        print(f"\nExported to: {output_path}")
        return output_path

    def get_summary(self) -> Dict:
        """
        Get summary statistics

        Returns:
            Dict with summary stats
        """
        if not self.combined_data:
            return {}

        total = len(self.combined_data)
        with_pdf = sum(1 for p in self.combined_data if p.get('pdf_data'))
        with_deadlines = sum(
            1 for p in self.combined_data
            if p.get('pdf_data') and p['pdf_data'].get('deadline')
        )

        return {
            'total_programs': total,
            'with_pdf_data': with_pdf,
            'with_deadlines': with_deadlines,
            'html_only': total - with_pdf
        }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='MZe National Grants Scraper')
    parser.add_argument(
        '--year',
        type=int,
        default=CURRENT_YEAR,
        help=f'Year to scrape (default: {CURRENT_YEAR})'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output JSON filename'
    )

    args = parser.parse_args()

    # Run scraper
    scraper = MZeGrantsScraper(year=args.year)
    scraper.scrape_all()

    # Show summary
    summary = scraper.get_summary()
    print("\n=== Summary ===")
    print(f"Total programs: {summary['total_programs']}")
    print(f"With PDF data: {summary['with_pdf_data']}")
    print(f"With deadlines: {summary['with_deadlines']}")
    print(f"HTML only: {summary['html_only']}")

    # Export
    scraper.export_json(args.output)


if __name__ == '__main__':
    main()
