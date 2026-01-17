# Czech Grants Scraper

**Apify Actor** pro scrapování českých grantů, EU fondů a dalších zdrojů financování.

## Podporované zdroje

### Grantové programy (implementováno)

| Zdroj | Doména | Program |
|-------|--------|---------|
| dotaceeu.cz | dotaceeu.cz | Hlavní databáze dotací (primární zdroj) |
| OP ST | opst.cz | Operační program Spravedlivá transformace |
| MV | mv.gov.cz | OP Národní spolupráce na hranicích a vízová politika |
| OP ŽP | opzp.cz | Operační program Životní prostředí |
| NRB | nrb.cz | Národní rozvojová banka |
| ESF | esfcr.cz | Evropský sociální fond (zaměstnanost) |
| OP TAK | optak.gov.cz | Operační program Technologie a aplikace pro konkurenceschopnost |
| SFŽP | sfzp.cz | Státní fond životního prostředí (Modernizační fond) |
| IROP | irop.mmr.cz | Integrovaný regionální operační program |

### Charitativní organizace (plánováno)

Připraveno pro budoucí implementaci.

### Nadace (plánováno)

Připraveno pro budoucí implementaci.

## Použití na Apify Platform

### 1. Spuštění na Apify

Tento Actor je optimalizován pro běh na Apify platformě:

1. **Nahrání do Apify Console:**
   ```bash
   # Přihlášení
   apify login
   
   # Deployment
   apify push
   ```

2. **Konfigurace vstupu:**
   - `scrapeMode`: Zvolte `basic` (pouze dotaceeu.cz) nebo `deep` (včetně dokumentů)
   - `maxGrants`: Limit počtu grantů (0 = neomezeno)
   - `ngoOnly`: Filtrovat pouze granty pro NGO
   - `sources`: Vybrat specifické zdroje (prázdné = všechny)
   - `delays`: Prodlevy mezi požadavky (respektování serverů)

3. **Spuštění:**
   - Klikněte na "Start" v Apify Console
   - Data budou uložena do Datasetu
   - Logy dostupné v běhu Actora

### 2. Lokální development

```bash
# Klonování repozitáře
git clone https://github.com/chocholous/czech-grants-scraper.git
cd czech-grants-scraper

# Vytvoření virtuálního prostředí
python3.13 -m venv venv
source venv/bin/activate  # Linux/macOS
# nebo: venv\Scripts\activate  # Windows

# Instalace závislostí
pip install -e .

# Instalace Playwright prohlížečů
playwright install chromium

# Lokální spuštění
apify run
```

## Architektura

### Actor Structure

```
czech-grants-scraper/
├── .actor/                    # Apify Actor konfigurace
│   ├── actor.json             # Actor metadata
│   ├── input_schema.json      # Definice vstupních parametrů
│   └── dataset_schema.json    # Definice výstupních dat
├── src/
│   └── main.py                # Actor entry point (používá Crawlee)
├── scrapers/
│   ├── grants/                # Grantové scrapery
│   │   └── sources/           # Sub-scrapery pro jednotlivé zdroje
│   ├── charities/             # Charitativní scrapery (plánováno)
│   └── foundations/           # Nadační scrapery (plánováno)
├── Dockerfile                 # Docker image pro Apify
└── pyproject.toml             # Python dependencies
```

### Klíčové technologie

- **Apify SDK** (`apify>=2.0.0`) - Správa běhu Actora, storage, logging
- **Crawlee** (`crawlee[playwright]>=0.4.0`) - Web scraping framework
  - `PlaywrightCrawler` - Pro AJAX pagination na dotaceeu.cz
  - `BeautifulSoupCrawler` - Pro statické detail stránky (10x rychlejší)
- **Actor.log** - Bezpečné logování (automatické cenzurování API klíčů)
- **Actor.push_data()** - Ukládání do Datasetu
- **Actor.set_value()** - Ukládání dokumentů do Key-Value Store

### Výhody Apify implementace

1. **Škálovatelnost**: Běží v cloudu, automatická správa zdrojů
2. **Storage**: Dataset pro strukturovaná data, KVS pro dokumenty
3. **Monitoring**: Vestavěné logy, metriky, alerty
4. **Scheduling**: Pravidelné spouštění (např. denně)
5. **API**: Přístup k datům přes Apify API
6. **Bezpečnost**: Actor.log censors API keys a credentials

## Konfigurace scraperů

### Input Schema (`.actor/input_schema.json`)

Definuje vstupní parametry pro Actor. Uživatel je konfiguruje v Apify Console.

### Dataset Schema (`.actor/dataset_schema.json`)

Definuje strukturu výstupních dat. Každý grant má:
- `external_id` - Unikátní identifikátor
- `title` - Název grantu
- `source_url` - URL detail stránky
- `operational_programme` - Operační program
- `call_status` - Stav výzvy (Otevřená/Uzavřená)
- `submission_deadline` - Uzávěrka příjmu žádostí
- `is_ngo_eligible` - Způsobilost pro NGO
- `total_allocation` - Celková alokace
- ... a další metadata

## Output

### Dataset

Strukturovaná data o grantech v JSON formátu:

```json
{
  "external_id": "10_25_102",
  "title": "102. výzva - Revitalizace ...",
  "source_url": "https://www.dotaceeu.cz/...",
  "operational_programme": "OP Spravedlivá transformace",
  "call_status": "Otevřená",
  "submission_deadline": "2026-03-05T00:00:00",
  "is_ngo_eligible": false,
  "total_allocation": 215000000,
  ...
}
```

### Key-Value Store (deep mode)

Při zapnutém deep scraping:
- `deep_{external_id}` - Plný obsah grantu (description, dokumenty)
- Dokumenty ke stažení (PDF, XLSX, DOCX)
- Konverze dokumentů na markdown

## Development

### Přidání nového sub-scraperu

1. Vytvořte třídu dědící z `AbstractGrantSubScraper`
2. Implementujte metody:
   - `can_handle(url)` - Rozpoznání domény
   - `extract_content(url, metadata)` - Extrakce obsahu
   - `download_document(url, path)` - Stažení dokumentů
3. Registrujte v `src/main.py`:
   ```python
   scraper_registry.register(NovyScraper())
   ```

Viz [docs/adding-scrapers.md](docs/adding-scrapers.md) pro detaily.

### Testing

```bash
# Spustit s limitem (development)
apify run

# V input.json nastavte:
{
  "maxGrants": 5,
  "scrapeMode": "basic"
}
```

## Jak přispět

1. Forkněte repozitář
2. Vytvořte feature branch (`git checkout -b feature/novy-scraper`)
3. Commitněte změny (`git commit -am 'Přidán scraper pro xyz'`)
4. Pushněte branch (`git push origin feature/novy-scraper`)
5. Vytvořte Pull Request

## Apify Resources

- [Apify Documentation](https://docs.apify.com)
- [Crawlee Documentation](https://crawlee.dev)
- [Actor Specification](https://raw.githubusercontent.com/apify/actor-whitepaper/refs/heads/master/README.md)

## Licence

MIT License - viz [LICENSE](LICENSE)
