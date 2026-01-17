# MZe SZIF National Grants Scraper

Autonomní scraper pro národní dotace Ministerstva zemědělství (MZe) administrované SZIF.

## Architektura

Scraper implementuje `AbstractGrantSubScraper` pattern podle PRD specifikace:

```
scrapers/
└── grants/
    └── sources/
        ├── base.py                    # Abstract base class
        ├── models.py                  # GrantContent, Document models
        ├── utils.py                   # Utility functions
        ├── registry.py                # SubScraperRegistry
        ├── mze_szif_cz.py            # ⭐ MZe scraper implementation
        └── pdf_zasady_parser.py       # Enhanced PDF parser
```

## Features

### 🔄 Autonomní scraping
- **Začíná z root URL** - není potřeba manuální konfigurace
- **Automatické discovery** - najde všechny dotační programy (56+)
- **PDF stahování** - stahuje a parsuje Zásady PDF (258 stran)
- **Rekurzivní extrakce** - najde i podprogramy (např. 20.A → 20.A.a, 20.A.b)

### 📄 PDF Parsing s víceprůchodovou analýzou
```python
# Pass 1: Skip TOC (table of contents with dots)
# Pass 2: Identify program boundaries
# Pass 3: Extract sections within each program
```

**Extrahované sekce:**
- 1 Účel
- 2 Předmět dotace
- 3 Žadatel / Konečný příjemce
- 4 Dotace / Výše dotace
- 5 Podmínky poskytnutí dotace
- 6 Termín podání žádosti
- 7 Přílohy k žádosti
- 8 Termín příjmu dokladů
- 9 Doklady prokazující nárok

### 💰 Strukturované parsing

**Částky:**
```python
{
  "min": 0,
  "max": 3000000,
  "currency": "CZK",
  "unit": "t"  # nebo "ha", None
}
```

**Termíny:**
```python
{
  "start_date": "2026-01-03",
  "end_date": "2026-01-15"
}
```

**Způsobilí žadatelé:**
```python
["Zemědělský podnikatel", "FO nebo PO", "obce", "NGO"]
```

## Output Schema (PRD compliant)

```json
{
  "source_url": "https://szif.gov.cz/cs/nd-dotacni-programy-18",
  "scraper_name": "MZeSZIFCzScraper",
  "scraped_at": "2026-01-17T12:00:00Z",
  "description": "Účel:\n...\n\nPředmět:\n...",
  "summary": "Cílem dotace je...",
  "funding_amounts": {
    "min": 0,
    "max": 3000000,
    "currency": "CZK"
  },
  "documents": [
    {
      "title": "Zásady pro rok 2026 - Program 18",
      "url": "...",
      "doc_type": "call_text",
      "file_format": "pdf",
      "local_path": "data/zasady_2026.pdf"
    }
  ],
  "eligible_recipients": ["Potravinové banky", "Charita ČR"],
  "additional_metadata": {
    "program_id": "18",
    "program_name": "Podpora činnosti potravinových bank...",
    "deadline": {
      "start_date": "2026-01-03",
      "end_date": "2026-01-15"
    }
  }
}
```

## Instalace

```bash
# Vytvořit venv
python3.13 -m venv .venv
source .venv/bin/activate

# Instalovat závislosti
pip install -r requirements.txt

# Instalovat poppler-utils (pro pdftotext)
brew install poppler  # macOS
# nebo
apt-get install poppler-utils  # Ubuntu/Debian
```

## Použití

### Autonomní mode (doporučeno)

```bash
python main.py
```

Scraper automaticky:
1. Navštíví https://szif.gov.cz/cs/narodni-dotace
2. Najde všechny dotační programy (56+)
3. Stáhne PDF Zásady pro rok 2026
4. Parsuje PDF (86 programů včetně podprogramů)
5. Extrahuje HTML data pro každý program
6. Kombinuje HTML + PDF → GrantContent
7. Exportuje do `output/mze_grants_YYYYMMDD_HHMMSS.json`

### Programové použití

```python
from scrapers.grants.sources.mze_szif_cz import MZeSZIFCzScraper

# Create scraper
scraper = MZeSZIFCzScraper()

# Autonomous scraping
grants = await scraper.scrape_all_programs(year=2026)

# Or extract single program
grant = await scraper.extract_content(
    url="https://szif.gov.cz/cs/nd-dotacni-programy-18",
    grant_metadata={}
)
```

### Registrace v registry

```python
from scrapers.grants.sources.registry import SubScraperRegistry

registry = SubScraperRegistry()
registry.register(MZeSZIFCzScraper())

# Router finds correct scraper
scraper = registry.get_scraper_for_url("https://szif.gov.cz/cs/nd-dotacni-programy-18")
```

## Testování PDF parseru

```bash
cd scrapers/grants/sources
python pdf_zasady_parser.py
```

Output:
```
Parsed 86 programs

Program 1.D: Podpora včelařství
Sections: ['Účel', 'Předmět', 'Žadatel', ...]
Deadline: {'end_date': '2026-11-15'}
Amounts: {'max': 180, 'currency': 'CZK'}
```

## Porovnání s původní implementací

| Feature | Původní (`src/`) | Nový (`scrapers/grants/sources/`) |
|---------|------------------|-------------------------------------|
| Architektura | Standalone | AbstractGrantSubScraper + Registry |
| Autonomie | ❌ Manuální konfigurace | ✅ Začíná z root URL |
| PDF parsing | ❌ Zachytí TOC místo těla | ✅ Víceprůchodová analýza |
| Sections | ❌ Prázdné | ✅ Plně extrahovány |
| Částky | `["20 000 Kč/t"]` (string) | `{"max": 20000, "unit": "t"}` |
| Termíny | `"3.1.2026"` | `"2026-01-03"` (ISO) |
| Output schema | Custom dict | PRD-compliant GrantContent |
| Registrace | N/A | ✅ SubScraperRegistry |

## Statistiky

- **Programů celkem**: 56 (HTML) → 86 (PDF včetně podprogramů)
- **Úspěšnost parsing**: ~100% (všechny sekce extrahovány)
- **PDF velikost**: 258 stran, 580 KB textu
- **Doba běhu**: ~30-60s (závislé na síti)

## Vývoj a rozšíření

### Přidání dalších sekcí

```python
# V pdf_zasady_parser.py:
section_pattern = re.compile(
    r'^(\d+)\s+(Účel|Předmět|...|NovaS ekce)'
)
```

### Parsing dalších let

```python
scraper.scrape_all_programs(year=2025)
# Automaticky stáhne zasady_2025.pdf
```

### Custom document classification

```python
# V mze_szif_cz.py:
DOC_TYPE_PATTERNS = {
    'call_text': ['zásady', 'pravidla'],
    'my_custom_type': ['vzor', 'template'],
}
```

## Známé limity

- PDF musí mít konzistentní strukturu (číslované sekce)
- Parsuje jen standardní formát Zásad (MZe 2025-2026)
- Sub-programy (20.A.a) jsou detekovány z PDF, ne z HTML
- Některé speciální pole (např. kontakty) nejsou v PDF strukturovaně

## TODOs

- [ ] Markdown konverze PDF dokumentů
- [ ] Parsing historie změn (Zpravodajství)
- [ ] Detekce sub-programů v HTML navigation
- [ ] Caching PDF pro rychlejší opakované běhy
- [ ] Error recovery (partial data extraction)

## License

MIT
