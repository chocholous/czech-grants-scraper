"""
HTML scraper for SZIF national grants website
Extracts basic information about grant programs from HTML pages
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from config import SZIF_BASE_URL, SZIF_PROGRAMY_LIST_URL, USER_AGENT


class SZIFHTMLScraper:
    """Scraper for SZIF HTML pages"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def get_program_list(self) -> List[Dict[str, str]]:
        """
        Get list of all grant programs from programs list page

        Returns:
            List of dicts with program_id, program_url, name
        """
        response = self.session.get(SZIF_PROGRAMY_LIST_URL)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml')
        programs = []

        # Find all program links matching pattern /cs/nd-dotacni-programy-*
        # Note: links are in nested <ul> inside side navigation
        program_links = soup.find_all('a', href=re.compile(r'/cs/nd-dotacni-programy-[\w\-]+'))

        for link in program_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Extract program ID from URL (e.g., "18" from "/cs/nd-dotacni-programy-18")
            match = re.search(r'/cs/nd-dotacni-programy-([\w\-]+)$', href)
            if match:
                program_id = match.group(1).upper()
                programs.append({
                    'program_id': program_id,
                    'program_url': f"{SZIF_BASE_URL}{href}",
                    'name': text
                })

        return programs

    def get_program_detail(self, program_url: str) -> Dict[str, any]:
        """
        Get detail information from program page

        Args:
            program_url: Full URL to program detail page

        Returns:
            Dict with description, news items, documents
        """
        response = self.session.get(program_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml')

        result = {
            'description': '',
            'news': [],
            'documents': []
        }

        # Extract description
        desc_div = soup.find('div', class_='section')
        if desc_div:
            # Get H2 title and following text
            h2 = desc_div.find('h2')
            if h2:
                # Get text after H2 but before next section
                desc_text = []
                for sibling in h2.find_next_siblings():
                    if sibling.name == 'div' and 'section' in sibling.get('class', []):
                        break
                    desc_text.append(sibling.get_text(strip=True))
                result['description'] = ' '.join(desc_text)

        # Extract news items
        news_section = soup.find('div', class_='section news')
        if news_section:
            news_items = news_section.find_all('li', class_='file')
            for item in news_items:
                h4 = item.find('h4')
                meta = item.find('div', class_='meta')
                link = item.find('a')

                if h4 and link:
                    result['news'].append({
                        'title': h4.get_text(strip=True),
                        'date': meta.get_text(strip=True) if meta else '',
                        'url': f"{SZIF_BASE_URL}{link.get('href', '')}"
                    })

        # Extract documents
        docs_section = soup.find('div', class_='section documents')
        if docs_section:
            doc_links = docs_section.find_all('a', href=re.compile(r'\.pdf'))
            for link in doc_links:
                href = link.get('href', '')
                if href.startswith('/cs/CmDocument'):
                    result['documents'].append({
                        'title': link.get_text(strip=True),
                        'url': f"{SZIF_BASE_URL}{href}"
                    })

        return result


if __name__ == '__main__':
    # Test the scraper
    scraper = SZIFHTMLScraper()

    print("Fetching program list...")
    programs = scraper.get_program_list()
    print(f"Found {len(programs)} programs")

    if programs:
        print(f"\nFirst 5 programs:")
        for prog in programs[:5]:
            print(f"  {prog['program_id']}: {prog['name']}")

        # Test detail scraping
        print(f"\nFetching detail for program {programs[0]['program_id']}...")
        detail = scraper.get_program_detail(programs[0]['program_url'])
        print(f"  Description: {detail['description'][:100]}...")
        print(f"  News items: {len(detail['news'])}")
        print(f"  Documents: {len(detail['documents'])}")
