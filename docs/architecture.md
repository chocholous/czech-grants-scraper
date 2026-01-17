# Architektura systému

## Přehled

Czech Grants Scraper je modulární systém pro sběr dat o grantech a dotacích z různých zdrojů.

## Komponenty

### 1. Orchestrátor (`scrapers/grants/dotaceeu.py`)

Hlavní řídící komponenta, která:
- Načítá konfiguraci z `config.yml`
- Inicializuje Playwright prohlížeč
- Koordinuje spouštění jednotlivých scraperů
- Agreguje výsledky do jednotného formátu

### 2. Base Scraper (`scrapers/grants/sources/base.py`)

Abstraktní třída definující rozhraní pro všechny scrapery:
- `scrape()` - hlavní metoda pro sběr dat
- `parse_grant()` - parsování jednotlivého grantu
- Společné utility pro HTTP requesty a DOM parsing

### 3. Modely (`scrapers/grants/sources/models.py`)

Datové modely:
- `Grant` - reprezentace grantu s poli jako název, částka, deadline, atd.
- `GrantSource` - metadata o zdroji dat

### 4. Registry (`scrapers/grants/sources/registry.py`)

Registr všech dostupných scraperů:
- Automatická registrace pomocí dekorátorů
- Lookup podle názvu nebo domény

### 5. Utils (`scrapers/grants/sources/utils.py`)

Sdílené utility:
- Document converter (PDF, DOCX, XLSX → Markdown)
- HTML parsing helpers
- Date parsing

## Datový tok

```
[Webové stránky] → [Scraper] → [Parser] → [Model] → [JSON výstup]
```

## Konfigurace

```yaml
# config.yml
sources:
  - name: opst_cz
    enabled: true
  - name: mv_gov_cz
    enabled: true

output:
  format: json
  directory: ./data
```

## Přidání nového scraperu

1. Vytvořte nový soubor v `scrapers/grants/sources/`
2. Implementujte třídu dědící z `BaseScraper`
3. Registrujte pomocí `@register_scraper` dekorátoru
4. Přidejte do `config.yml`

Viz [adding-scrapers.md](adding-scrapers.md) pro detailní návod.
