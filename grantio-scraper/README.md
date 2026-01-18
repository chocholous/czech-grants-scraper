# Grants Scraper

Modulární scraping systém pro české granty a dotace.

## Architektura

```
grants_scraper/
├── core/           # Stabilní jádro (modely, HTTP klient, normalizery)
├── navigators/     # Strategie pro discovery (single-level, multi-level)
├── parsers/        # Strategie pro extrakci (HTML, PDF, tabulky)
├── plugins/        # Volitelné rozšíření (PDF, Excel, LLM)
├── config/         # YAML konfigurace zdrojů
└── orchestrator.py # Master koordinátor
```

## Instalace

```bash
# Základní instalace
pip install -e .

# S PDF podporou
pip install -e ".[pdf]"

# S vývojovými nástroji
pip install -e ".[dev]"

# Vše
pip install -e ".[all]"
```

## Použití

### CLI

```bash
# Scrapovat všechny zdroje
python -m grants_scraper --mode full

# Scrapovat konkrétní zdroje
python -m grants_scraper --sources mzd_gov,mfcr

# Dry run (pouze discovery)
python -m grants_scraper --dry-run

# Omezit počet grantů (pro testování)
python -m grants_scraper --sources mzd_gov --max-grants 5
```

### Programaticky

```python
import asyncio
from grants_scraper.orchestrator import run_scraper

grants = asyncio.run(run_scraper(
    sources=["mzd_gov"],
    max_grants=10,
))

for grant in grants:
    print(f"{grant.title} - {grant.deadline}")
```

## Konfigurace zdrojů

Zdroje se definují v `config/sources.yml`:

```yaml
sources:
  - source_id: mzd_gov
    source_name: "Ministerstvo zdravotnictví ČR"
    base_url: "https://www.mzd.gov.cz"
    listing_url: "https://www.mzd.gov.cz/dotacni-programy"
    listing_selector: "a[href*='/dotacni-programy/']"
    navigator: single_level
    parser: html_detail
```

## Testy

```bash
# Spustit všechny testy
pytest

# S coverage
pytest --cov=grants_scraper

# Pouze unit testy
pytest tests/unit/
```

## Vývoj

```bash
# Type checking
mypy grants_scraper/

# Linting
ruff check grants_scraper/
```
