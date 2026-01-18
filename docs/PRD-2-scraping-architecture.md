# PRD-2: Master Scraper Architecture

## Executive Summary

Architektura pro scraping 190+ zdrojů grantů v ČR. Místo 190 individuálních scraperů používáme **5 scraper families + konfigurace**. Modulární design s 5 vrstvami zajišťuje rozšiřitelnost a maintainability.

**Aktuální stav:** 28 scraperů, 15% coverage
**Cílový stav:** 190 zdrojů, 100% coverage

---

## 1. Gap Analysis

### 1.1 Katalog zdrojů (research/05-grant-sources-catalog.yaml)

| Kategorie | Počet | Implementováno | Chybí |
|-----------|-------|----------------|-------|
| Ministerstva | 14 | 10 | 4 |
| Agentury | 7 | 6 | 1 |
| EU fondy (OP) | 7 | 5 | 2 |
| INTERREG | 6 | 0 | 6 |
| Kraje | 14 | 0 | 14 |
| Města | 20 | 0 | 20 |
| Nadace | 23 | 0 | 23 |
| CSR (firmy) | 21 | 0 | 21 |
| MAS | 15 | 0 | 15 |
| Ostatní | 63 | 7 | 56 |
| **CELKEM** | **190** | **28** | **162** |

### 1.2 Typy zdrojů

```
┌─────────────────────────────────────────────────────────────────┐
│                         ZDROJE GRANTŮ                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │   AGREGÁTORY    │    │  PRIMÁRNÍ       │                    │
│  │                 │    │  ZDROJE         │                    │
│  │  dotaceeu.cz    │    │                 │                    │
│  │  grantika.cz    │    │  Ministerstva   │                    │
│  │  enovation.cz   │    │  Agentury       │                    │
│  │  ...            │    │  OP fondy       │                    │
│  │                 │    │  Kraje          │                    │
│  │  Brief info +   │    │  Města          │                    │
│  │  link to source │    │  Nadace         │                    │
│  └─────────────────┘    │  ...            │                    │
│         │               │                 │                    │
│         │               │  Full details   │                    │
│         ▼               │  + documents    │                    │
│  ┌─────────────────┐    └─────────────────┘                    │
│  │ Listing může    │              │                            │
│  │ být single/     │              │                            │
│  │ multi-level     │◀─────────────┘                            │
│  │ (stejné jako    │                                           │
│  │ primární)       │                                           │
│  └─────────────────┘                                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  STATIC SOURCES (single-grant)                          │   │
│  │                                                          │   │
│  │  Nadace bez konkrétních výzev - jen účel/focus:         │   │
│  │  - Nadace XY podporuje ekologii (bez deadline, budget)   │   │
│  │  - Firemní CSR program (obecná podpora oblasti)          │   │
│  │  → Scrapujeme jako grant_type: "ongoing_program"         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Klíčový insight:** Agregátory i primární zdroje používají stejné navigátory (single/multi-level). Rozdíl je v tom, co dělají s výsledkem:
- **Agregátor:** listing → brief info + odkaz na primární zdroj
- **Primární:** listing → full detail page + dokumenty

---

## 2. Discovery Layer (Klíčová inovace)

### 2.1 Problém

Webové stránky mají hierarchickou strukturu. Příklad MZe:

```
mze.cz
└── /dotace/programy/
    ├── Program rozvoje venkova
    │   ├── Opatření 4.1.1
    │   │   ├── Výzva 2026-01 → detail + PDF
    │   │   └── Výzva 2026-02 → detail + PDF
    │   └── Opatření 4.2.1
    │       └── Výzva 2026-03 → detail + PDF
    └── Národní dotace
        └── ...
```

### 2.2 Navigator Strategie

```
┌─────────────────────────────────────────────────────────────────┐
│                     DISCOVERY LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              NavigatorStrategy (abstract)                 │  │
│  │                                                           │  │
│  │  async def discover(start_url) -> List[GrantTarget]       │  │
│  │  async def navigate_level(url, level) -> List[url]        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                    │
│     ┌──────────────────────┼──────────────────────┐            │
│     ▼                      ▼                      ▼            │
│  ┌───────────┐      ┌───────────┐          ┌───────────┐       │
│  │ SingleLvl │      │ MultiLvl  │          │ Document  │       │
│  │ Navigator │      │ Navigator │          │ Navigator │       │
│  │           │      │           │          │           │       │
│  │ listing → │      │ L1 → L2 → │          │ listing → │       │
│  │ detail    │      │ L3 → ...  │          │ PDF/Excel │       │
│  │           │      │ → detail  │          │ → parse   │       │
│  └───────────┘      └───────────┘          └───────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Navigator Types

| Navigator | Použití | Příklady zdrojů |
|-----------|---------|-----------------|
| `SingleLevelNavigator` | list → detail | Jednoduché weby, některé nadace, agregátory |
| `MultiLevelNavigator` | L1 → L2 → ... → detail | Ministerstva, kraje, OP fondy, agregátory s kategoriemi |
| `DocumentNavigator` | list → PDF/Excel | SZIF, SFŽP, některé nadace |
| `HybridNavigator` | kombinace výše | MZe (HTML + PDF), města |
| `StaticNavigator` | single page = single grant | Nadace s jedním účelem, CSR programy |

**Poznámka:** `SingleLevelNavigator` a `MultiLevelNavigator` fungují stejně pro agregátory i primární zdroje. Liší se pouze parser (co se dělá s výsledkem discovery).

### 2.4 Static Sources (Single-Grant)

Některé zdroje nemají listing - celý web popisuje jeden program/účel:

```yaml
# sources.yml - static source example
nadace_xyz:
  id: nadace_xyz
  name: Nadace XYZ
  navigator: StaticNavigator
  url: https://www.nadace-xyz.cz/podporujeme

  # Není listing, jen jeden "grant"
  grant_type: ongoing_program  # vs "call" pro výzvy s deadline

  parser: StaticPageParser
  selectors:
    name: "h1"
    focus_areas: ".podporujeme-oblasti li"
    description: ".o-nadaci"
    contact: ".kontakt"
    # Bez deadline, budget - ongoing program
```

**Grant types:**
- `call` - konkrétní výzva s deadline, rozpočtem, eligibility
- `ongoing_program` - trvalý program bez konkrétních termínů
- `grant_scheme` - schéma/pravidla (meta-level)

### 2.5 Konfigurace pro Multi-Level

```yaml
# sources.yml
mze:
  id: mze
  name: Ministerstvo zemědělství
  navigator: MultiLevelNavigator
  levels:
    - name: programs
      url: https://mze.gov.cz/public/portal/dotace/programy
      selector: ".program-list .item a"
    - name: subprograms
      selector: ".subprogram-list .item a"
    - name: grants
      selector: ".grant-list .item a"
      is_terminal: true
  detail:
    parser: HtmlDetailParser
```

---

## 3. Pětivrstvá Architektura

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Layer 5: CUSTOM SCRAPERS (10%)                                 │
│  ─────────────────────────────────────────────────────────────  │
│  Escape hatch pro edge cases. Plná kontrola.                    │
│  Příklady: API-only zdroje, JavaScript-heavy weby               │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 4: CONFIGURATION (sources.yml)                           │
│  ─────────────────────────────────────────────────────────────  │
│  190 zdrojů jako YAML konfigurace. Žádný kód.                   │
│  Definuje: URL, selektory, navigator type, parser type          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 3: PLUGINS (Optional)                                    │
│  ─────────────────────────────────────────────────────────────  │
│  PDF Parser, Excel Parser, LLM Extractor, OCR                   │
│  Registrují se, volají se podle potřeby                         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 2: STRATEGIES (Families)                                 │
│  ─────────────────────────────────────────────────────────────  │
│  5 Navigator strategies + 5 Parser strategies                   │
│  Znovupoužitelná logika, parametrizovaná konfigurací            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: CORE (Stable)                                         │
│  ─────────────────────────────────────────────────────────────  │
│  Pipeline, HTTP client, Selectors, Normalization, Dedup         │
│  Mění se zřídka, high test coverage                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Layer 1: Core

```python
# core/pipeline.py
class ScrapingPipeline:
    """Orchestruje celý scraping process"""

    async def run(self, source: SourceConfig) -> List[Grant]:
        # 1. Discovery
        navigator = self.get_navigator(source.navigator_type)
        targets = await navigator.discover(source)

        # 2. Extraction
        parser = self.get_parser(source.parser_type)
        grants = []
        for target in targets:
            grant = await parser.extract(target)
            grants.append(grant)

        # 3. Normalization
        grants = [self.normalizer.normalize(g) for g in grants]

        # 4. Deduplication
        grants = self.deduplicator.deduplicate(grants)

        return grants

# core/http_client.py
class HttpClient:
    """Rate-limited, cached, retry-enabled HTTP client"""

    async def get(self, url: str) -> Response:
        # Rate limiting per domain
        # Retry with exponential backoff
        # Response caching
        # User-agent rotation

# core/selectors.py
class SelectorEngine:
    """CSS + XPath + Regex unified selector"""

    def select(self, html: str, selector: SelectorConfig) -> List[str]:
        # Supports: CSS, XPath, regex, jsonpath
        # Fallback chain: try selector1, if empty try selector2

# core/normalizer.py
class GrantNormalizer:
    """Normalizuje data do PRD schema"""

    def normalize(self, raw: dict) -> Grant:
        # Date parsing (various formats)
        # Amount parsing (CZK, EUR, "5 mil.", "5.000.000")
        # URL normalization
        # Text cleanup (HTML entities, whitespace)

# core/deduplicator.py
class Deduplicator:
    """Hash-based deduplication"""

    def get_hash(self, grant: Grant) -> str:
        content = f"{grant.source_id}|{grant.url}|{grant.title}|{grant.deadline}"
        return hashlib.sha256(content.encode()).hexdigest()

    def deduplicate(self, grants: List[Grant]) -> List[Grant]:
        # Primary source wins over aggregator
        # Keep source_refs from duplicates
```

### 3.2 Layer 2: Strategies

#### Navigator Strategies

```python
# strategies/navigators/single_level.py
class SingleLevelNavigator(NavigatorStrategy):
    """Jednoduchý list → detail pattern"""

    async def discover(self, source: SourceConfig) -> List[GrantTarget]:
        listing_html = await self.http.get(source.listing_url)
        links = self.selectors.select(listing_html, source.listing_selector)
        return [GrantTarget(url=link, source=source) for link in links]

# strategies/navigators/multi_level.py
class MultiLevelNavigator(NavigatorStrategy):
    """Hierarchická navigace přes N úrovní"""

    async def discover(self, source: SourceConfig) -> List[GrantTarget]:
        targets = []
        await self._traverse_level(source.levels[0].url, source.levels, 0, targets)
        return targets

    async def _traverse_level(self, url, levels, depth, targets):
        html = await self.http.get(url)
        links = self.selectors.select(html, levels[depth].selector)

        if levels[depth].is_terminal:
            targets.extend([GrantTarget(url=link) for link in links])
        else:
            for link in links:
                await self._traverse_level(link, levels, depth + 1, targets)

# strategies/navigators/document.py
class DocumentNavigator(NavigatorStrategy):
    """Navigace kde data jsou v PDF/Excel"""

    async def discover(self, source: SourceConfig) -> List[GrantTarget]:
        listing_html = await self.http.get(source.listing_url)
        doc_links = self.selectors.select(listing_html, source.document_selector)
        return [GrantTarget(url=link, is_document=True) for link in doc_links]

# strategies/navigators/static.py
class StaticNavigator(NavigatorStrategy):
    """Pro zdroje s jedním grantem (celý web = jeden program)"""

    async def discover(self, source: SourceConfig) -> List[GrantTarget]:
        # Žádný listing - URL sama o sobě je grant
        return [GrantTarget(
            url=source.url,
            source_id=source.id,
            grant_type=source.grant_type or "ongoing_program"
        )]
```

#### Parser Strategies

```python
# strategies/parsers/html_detail.py
class HtmlDetailParser(ParserStrategy):
    """Parsuje HTML detail stránku"""

    async def extract(self, target: GrantTarget, source: SourceConfig) -> dict:
        html = await self.http.get(target.url)
        return {
            "title": self.selectors.select_one(html, source.selectors.title),
            "description": self.selectors.select_one(html, source.selectors.description),
            "deadline": self.selectors.select_one(html, source.selectors.deadline),
            "documents": self._extract_documents(html, source.selectors.documents),
        }

# strategies/parsers/pdf_parser.py
class PdfParser(ParserStrategy):
    """Extrahuje data z PDF dokumentu"""

    async def extract(self, target: GrantTarget, source: SourceConfig) -> dict:
        pdf_bytes = await self.http.get_binary(target.url)
        text = self.plugins.pdf.extract_text(pdf_bytes)

        # Structured extraction based on patterns
        return {
            "title": self._extract_title(text, source.patterns),
            "deadline": self._extract_deadline(text, source.patterns),
            # ...
        }

# strategies/parsers/table_parser.py
class TableParser(ParserStrategy):
    """Parsuje HTML/Excel tabulky s granty"""

    async def extract(self, target: GrantTarget, source: SourceConfig) -> List[dict]:
        if target.url.endswith('.xlsx'):
            return self.plugins.excel.parse(target.url, source.table_config)
        else:
            html = await self.http.get(target.url)
            return self._parse_html_table(html, source.table_config)

# strategies/parsers/static_page.py
class StaticPageParser(ParserStrategy):
    """Parsuje single-grant stránku (nadace s jedním účelem)"""

    async def extract(self, target: GrantTarget, source: SourceConfig) -> dict:
        html = await self.http.get(target.url)
        return {
            "title": self.selectors.select_one(html, source.selectors.name),
            "description": self.selectors.select_one(html, source.selectors.description),
            "focus_areas": self.selectors.select_all(html, source.selectors.focus_areas),
            "contact": self.selectors.select_one(html, source.selectors.contact),
            "grant_type": target.grant_type or "ongoing_program",
            # Bez deadline, budget - ongoing program
        }
```

### 3.3 Layer 3: Plugins

```python
# plugins/pdf/__init__.py
class PdfPlugin:
    """PDF text extraction + parsing"""

    def extract_text(self, pdf_bytes: bytes) -> str:
        # pdfplumber / PyMuPDF

    def extract_tables(self, pdf_bytes: bytes) -> List[List[str]]:
        # Table extraction from PDF

# plugins/excel/__init__.py
class ExcelPlugin:
    """Excel/CSV parsing"""

    def parse(self, file_path: str, config: TableConfig) -> List[dict]:
        # openpyxl / pandas

# plugins/llm/__init__.py
class LlmPlugin:
    """LLM-based extraction for complex cases"""

    async def extract_structured(self, text: str, schema: dict) -> dict:
        # Call LLM API with structured output
```

### 3.4 Layer 4: Configuration

```yaml
# sources.yml
metadata:
  version: "2.0"
  generated: "2026-01-18"
  total_sources: 190

sources:
  # ═══════════════════════════════════════════════════════════════
  # MINISTERSTVA
  # ═══════════════════════════════════════════════════════════════

  mze:
    id: mze
    name: Ministerstvo zemědělství
    category: ministry
    domain: mze.gov.cz

    navigator: MultiLevelNavigator
    levels:
      - name: programs
        url: https://mze.gov.cz/public/portal/dotace/programy
        selector: ".program-list .item a"
      - name: grants
        selector: ".grant-list .item a"
        is_terminal: true

    parser: HtmlDetailParser
    selectors:
      title: "h1.page-title"
      description: ".grant-description"
      deadline: ".deadline-date"
      documents: ".document-list a[href$='.pdf']"

    rate_limit: 2  # requests per second

  # ───────────────────────────────────────────────────────────────

  szif:
    id: szif
    name: SZIF
    category: agency
    domain: szif.cz

    navigator: DocumentNavigator
    listing_url: https://www.szif.cz/cs/seznam-vyzev
    document_selector: "a.pdf-link"

    parser: PdfParser
    patterns:
      title: "^Název výzvy:\\s*(.+)$"
      deadline: "Termín.*?:\\s*(\\d{1,2}\\.\\d{1,2}\\.\\d{4})"
      amount: "Alokace.*?:\\s*([\\d\\s,]+)\\s*(Kč|EUR)"

  # ═══════════════════════════════════════════════════════════════
  # KRAJE
  # ═══════════════════════════════════════════════════════════════

  praha:
    id: praha
    name: Hlavní město Praha
    category: region
    domain: granty.praha.eu

    navigator: SingleLevelNavigator
    listing_url: https://granty.praha.eu/vyzvy
    listing_selector: ".grant-item a.title"

    parser: HtmlDetailParser
    selectors:
      title: "h1"
      description: ".description"
      deadline: "[data-field='deadline']"
      amount_min: "[data-field='min-amount']"
      amount_max: "[data-field='max-amount']"

  # ... dalších 187 zdrojů
```

### 3.5 Layer 5: Custom Scrapers

```python
# custom/csas_nadace.py
class CSASNadaceScraper(CustomScraper):
    """
    ČSAS Nadace vyžaduje JavaScript rendering.
    Nelze řešit konfigurací, potřebuje Playwright.
    """

    SOURCE_ID = "csas_nadace"

    async def scrape(self) -> List[Grant]:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto("https://www.csas.cz/cs/nadace")
            # ... custom logic
```

---

## 4. Master Orchestrator

```python
# master/orchestrator.py
class MasterScraper:
    """
    Orchestruje celý scraping process:
    1. Agregátory (dotaceeu.cz → brief + odkaz)
    2. Primární zdroje (ministerstva, kraje, nadace → full detail)
    3. Deduplikace (primární vyhrává)
    """

    def __init__(self, config_path: str = "sources.yml"):
        self.config = load_config(config_path)
        self.pipeline = ScrapingPipeline()
        self.deduplicator = Deduplicator()

    async def run(
        self,
        mode: str = "full",              # full | aggregator | primary
        sources: List[str] = None,       # None = all
        max_per_source: int = None,
        parallel: int = 5,
    ) -> List[Grant]:

        all_grants = []

        # 1. Agregátory (nízká priorita pro deduplikaci)
        if mode in ("full", "aggregator"):
            aggregator_grants = await self._run_aggregators()
            for g in aggregator_grants:
                g.priority = 10  # Nižší priorita
            all_grants.extend(aggregator_grants)

        # 2. Primární zdroje (vysoká priorita)
        if mode in ("full", "primary"):
            primary_sources = self._get_primary_sources(sources)

            # Paralelní scraping s limitem
            semaphore = asyncio.Semaphore(parallel)
            tasks = [
                self._scrape_source(src, semaphore, max_per_source)
                for src in primary_sources
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    for g in result:
                        g.priority = 1  # Vysoká priorita
                    all_grants.extend(result)

        # 3. Deduplikace
        return self.deduplicator.deduplicate(all_grants)

    async def _scrape_source(
        self,
        source: SourceConfig,
        semaphore: asyncio.Semaphore,
        max_grants: int = None
    ) -> List[Grant]:
        async with semaphore:
            try:
                grants = await self.pipeline.run(source)
                if max_grants:
                    grants = grants[:max_grants]
                return grants
            except Exception as e:
                logger.error(f"Failed to scrape {source.id}: {e}")
                return []
```

---

## 5. Deduplication Strategy

```python
class Deduplicator:
    """
    Deduplikace grantů z více zdrojů.

    Strategie:
    1. Hash = sha256(source_id + url + normalized_title + deadline)
    2. Primární zdroj (priority=1) vždy vyhrává nad agregátorem (priority=10)
    3. Zachováváme source_refs ze všech duplicit
    """

    def get_hash(self, grant: Grant) -> str:
        # Normalize title: lowercase, remove extra whitespace
        title = re.sub(r'\s+', ' ', grant.title.lower().strip())

        # Normalize deadline to ISO format
        deadline = grant.deadline.isoformat() if grant.deadline else ""

        content = f"{grant.source_id}|{grant.url}|{title}|{deadline}"
        return hashlib.sha256(content.encode()).hexdigest()

    def deduplicate(self, grants: List[Grant]) -> List[Grant]:
        seen: Dict[str, Grant] = {}

        # Sort by priority (lower = higher priority)
        sorted_grants = sorted(grants, key=lambda g: g.priority)

        for grant in sorted_grants:
            hash_key = self.get_hash(grant)

            if hash_key not in seen:
                seen[hash_key] = grant
            else:
                # Merge source_refs from duplicate
                existing = seen[hash_key]
                existing.source_refs.append({
                    "source_id": grant.source_id,
                    "url": grant.url,
                    "scraped_at": grant.scraped_at
                })

        return list(seen.values())
```

---

## 6. File Structure

```
scrapers/grants/
├── core/
│   ├── __init__.py
│   ├── pipeline.py           # ScrapingPipeline
│   ├── http_client.py        # Rate-limited HTTP
│   ├── selectors.py          # CSS/XPath/Regex
│   ├── normalizer.py         # Data normalization
│   └── deduplicator.py       # Hash-based dedup
│
├── strategies/
│   ├── __init__.py
│   ├── navigators/
│   │   ├── __init__.py
│   │   ├── base.py           # NavigatorStrategy ABC
│   │   ├── single_level.py   # list → detail
│   │   ├── multi_level.py    # L1 → L2 → ... → detail
│   │   ├── document.py       # list → PDF/Excel
│   │   ├── hybrid.py         # HTML + documents
│   │   ├── static.py         # single page = single grant
│   │   └── aggregator.py     # crawl + delegate
│   │
│   └── parsers/
│       ├── __init__.py
│       ├── base.py           # ParserStrategy ABC
│       ├── html_detail.py    # HTML page parser
│       ├── pdf_parser.py     # PDF extraction
│       ├── table_parser.py   # HTML/Excel tables
│       ├── static_page.py    # Single-grant pages
│       └── api_parser.py     # REST/GraphQL
│
├── plugins/
│   ├── __init__.py
│   ├── pdf/
│   │   └── __init__.py       # PdfPlugin
│   ├── excel/
│   │   └── __init__.py       # ExcelPlugin
│   └── llm/
│       └── __init__.py       # LlmPlugin
│
├── config/
│   ├── sources.yml           # 190 source configs
│   └── loader.py             # Config loader
│
├── custom/
│   ├── __init__.py
│   └── csas_nadace.py        # Example custom scraper
│
├── master/
│   ├── __init__.py
│   ├── orchestrator.py       # MasterScraper
│   └── __main__.py           # CLI entry point
│
└── sources/                  # Legacy (28 existing scrapers)
    ├── base.py
    ├── models.py
    └── *.py
```

---

## 7. CLI Interface

```bash
# Full scrape (všechny zdroje)
python -m scrapers.grants.master --mode full

# Pouze agregátory
python -m scrapers.grants.master --mode aggregator

# Pouze primární zdroje
python -m scrapers.grants.master --mode primary

# Konkrétní zdroje
python -m scrapers.grants.master --sources mze,szif,praha

# Limit per source (pro testování)
python -m scrapers.grants.master --max-per-source 5

# Paralelní scrapování
python -m scrapers.grants.master --parallel 10

# Dry run (jen discovery, bez extrakce)
python -m scrapers.grants.master --dry-run

# Výstup
python -m scrapers.grants.master --output json > grants.json
python -m scrapers.grants.master --output dataset  # Apify dataset
```

---

## 8. Implementation Waves

| Vlna | Zdroje | Počet | Popis |
|------|--------|-------|-------|
| **1** | Existující scrapery | 28 | Migrace na novou architekturu |
| **2** | Ministerstva + Agentury | 10 | Dokončení coverage |
| **3** | Kraje + TOP města | 20 | Praha, Brno, Ostrava, Plzeň, kraje |
| **4** | Agregátory | 5 | dotaceeu, grantika, enovation |
| **5** | Nadace + CSR | 40 | Top nadace a firemní programy |
| **6** | Zbytek | 87 | MAS, menší města, niche |

### Wave 1: Migrace (28 scraperů)

```yaml
# Migrace existujícího mze_cz.py na config
mze:
  id: mze
  migrated_from: sources/mze_cz.py
  navigator: SingleLevelNavigator  # Existující logika
  parser: HtmlDetailParser
  # ... selektory z existujícího kódu
```

### Wave 2: Ministerstva completion

| Zdroj | Navigator | Parser | Poznámka |
|-------|-----------|--------|----------|
| MŽP-NNO | SingleLevel | Html | Standardní web |
| MMR | MultiLevel | Html | 2 úrovně |
| MPSV | SingleLevel | Html | Standardní |
| HZS | SingleLevel | Html + Pdf | Kombinovaný |
| SFDI | SingleLevel | Html | Standardní |

---

## 9. Data Models (PRD Schema)

```python
@dataclass
class Grant:
    """Unified grant schema (PRD)"""

    # Identity
    record_type: str = "grant"
    source_id: str = ""
    source_name: str = ""
    grant_url: str = ""
    content_hash: str = ""

    # Type
    grant_type: str = "call"  # call | ongoing_program | grant_scheme

    # Core info
    title: str = ""
    description: str = ""
    summary: str = ""
    focus_areas: List[str] = field(default_factory=list)  # Pro ongoing_program

    # Dates
    deadline: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Funding
    amount_min: Optional[int] = None
    amount_max: Optional[int] = None
    amount_total: Optional[int] = None
    currency: str = "CZK"

    # Classification
    categories: List[str] = field(default_factory=list)
    eligible_recipients: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=list)

    # Documents
    documents: List[Document] = field(default_factory=list)

    # Meta
    extracted_at: datetime = field(default_factory=datetime.now)
    priority: int = 1  # 1=primary, 10=aggregator
    source_refs: List[dict] = field(default_factory=list)

@dataclass
class Document:
    """Attached document"""
    title: str
    url: str
    doc_type: str  # call_text, guidelines, template, budget, annex
    file_format: str  # pdf, docx, xlsx

@dataclass
class GrantTarget:
    """Discovery result - target to scrape"""
    url: str
    source_id: str
    is_document: bool = False
    metadata: dict = field(default_factory=dict)
```

---

## 10. Testing Strategy

```
tests/
├── unit/
│   ├── test_selectors.py       # Selector engine
│   ├── test_normalizer.py      # Data normalization
│   ├── test_deduplicator.py    # Deduplication logic
│   └── test_navigators.py      # Navigator strategies
│
├── integration/
│   ├── test_pipeline.py        # Full pipeline
│   └── test_sources.py         # Per-source tests
│
└── fixtures/
    ├── html/                   # Saved HTML pages
    │   ├── mze_listing.html
    │   └── mze_detail.html
    └── expected/               # Expected outputs
        └── mze_grants.json
```

### Test Pattern

```python
# tests/integration/test_sources.py
@pytest.mark.parametrize("source_id", ["mze", "szif", "praha"])
async def test_source_scraping(source_id: str):
    """Test that source config produces valid grants"""
    config = load_config()
    source = config.sources[source_id]

    pipeline = ScrapingPipeline()
    grants = await pipeline.run(source, max_grants=3)

    assert len(grants) > 0
    for grant in grants:
        assert grant.title
        assert grant.source_id == source_id
        assert grant.grant_url
```

---

## 11. Monitoring & Observability

```python
# Metrics to track
metrics = {
    "scraper_runs_total": Counter,
    "grants_scraped_total": Counter,
    "scraper_errors_total": Counter,
    "scraper_duration_seconds": Histogram,
    "source_freshness_seconds": Gauge,
}

# Alerting rules
alerts = [
    # Source hasn't been scraped in 7 days
    "source_freshness_seconds > 604800",

    # Error rate > 10%
    "scraper_errors_total / scraper_runs_total > 0.1",

    # No grants found (might indicate broken scraper)
    "grants_scraped_total == 0",
]
```

---

## 12. Summary

### Klíčové principy

1. **Configuration over Code** - 90% zdrojů jako YAML, 10% custom code
2. **Strategy Pattern** - Znovupoužitelné navigátory a parsery
3. **Plugin Architecture** - PDF, Excel, LLM jako volitelné pluginy
4. **Priority-based Deduplication** - Primární zdroj vždy vyhrává
5. **Graceful Degradation** - Selhání jednoho zdroje neovlivní ostatní

### Výhody oproti současnému stavu

| Aspekt | Současný stav | Nová architektura |
|--------|---------------|-------------------|
| Přidání zdroje | Nový Python soubor | YAML konfigurace |
| Discovery | Hardcoded nebo žádný | 5 Navigator strategií |
| Testování | Per-scraper | Unified test framework |
| Deduplikace | Žádná | Hash-based + priority |
| Maintainability | 28 souborů s duplicitním kódem | Core + Strategies + Config |

### Milestones

| Milestone | Deadline | Deliverable |
|-----------|----------|-------------|
| M1 | +2 weeks | Core layer (pipeline, http, selectors) |
| M2 | +4 weeks | Strategies (navigators, parsers) |
| M3 | +6 weeks | Config migration (28 sources → YAML) |
| M4 | +8 weeks | Wave 2-3 (ministerstva + kraje) |
| M5 | +12 weeks | Full 190 sources |

---

*Document version: 2.0*
*Last updated: 2026-01-18*
*Author: Claude + User collaboration*
