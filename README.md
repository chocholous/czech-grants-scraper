# Czech Grants Scraper

Kolekce scraperů pro české granty, EU fondy a další zdroje financování.

## Podporované zdroje

### Grantové programy (implementováno)

| Zdroj | Doména | Program |
|-------|--------|---------|
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

## Instalace

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
```

## Konfigurace

1. Zkopírujte `.env.example` do `.env`
2. Upravte hodnoty podle potřeby

```bash
cp .env.example .env
```

## Použití

### Základní spuštění

```bash
cd scrapers/grants
python dotaceeu.py
```

### Konfigurace scraperů

Upravte `scrapers/grants/config.yml` pro nastavení:
- Aktivních zdrojů
- Výstupního formátu
- Limitů a timeoutů

### Apify Actor

Scraper je dostupný jako Apify Actor. Podporované vstupní parametry:

| Parametr | Typ | Výchozí | Popis |
|----------|-----|---------|-------|
| `mode` | string | `refresh` | `refresh` = scrapovat, `search` = vyhledávat, `auto` = obojí |
| `maxGrants` | integer | - | Max počet grantů (pro testování) |
| `deepScrape` | boolean | `false` | Následovat odkazy na zdrojové weby |
| `enableLlm` | boolean | `false` | Povolit LLM obohacení dat |
| `llmModel` | string | `anthropic/claude-haiku-4.5` | Model pro LLM extrakci |
| `testUrls` | array | - | Testovat konkrétní URL s pod-scrapery |

#### LLM Enrichment

Funkce `enableLlm` používá LLM k extrakci strukturovaných informací z textu grantových výzev:

- **Kritéria způsobilosti** - kategorizovaná podle typu (žadatel, projekt, finanční, územní)
- **Hodnotící kritéria** - s body/váhami pokud jsou uvedeny
- **Podporované/nepodporované aktivity**
- **Požadované přílohy**
- **Tematická klíčová slova** - pro kategorizaci

Příklad použití:

```json
{
  "mode": "refresh",
  "deepScrape": true,
  "enableLlm": true,
  "llmModel": "anthropic/claude-haiku-4.5",
  "maxGrants": 5
}
```

Výstup obsahuje pole `enhancedInfo`:

```json
{
  "enhancedInfo": {
    "eligibility_criteria": [
      {"criterion": "Příjemcem musí být kraj", "category": "applicant", "is_mandatory": true}
    ],
    "territorial_restrictions": "Karlovarský kraj",
    "thematic_keywords": ["vouchery", "podnikání", "transformace"]
  }
}
```

LLM využívá [Apify OpenRouter Actor](https://apify.com/apify/openrouter) pro přístup k modelům.

## Struktura projektu

```
czech-grants-scraper/
├── scrapers/
│   ├── grants/           # Grantové scrapery
│   │   ├── sources/      # Jednotlivé zdroje
│   │   ├── dotaceeu.py   # Hlavní orchestrátor
│   │   └── config.yml    # Konfigurace
│   ├── charities/        # Charitativní scrapery (plánováno)
│   └── foundations/      # Nadační scrapery (plánováno)
├── docs/                 # Dokumentace
├── utils/                # Sdílené utility
├── data/                 # Výstupní data
└── tests/                # Testy
```

## Jak přispět

1. Forkněte repozitář
2. Vytvořte feature branch (`git checkout -b feature/novy-scraper`)
3. Commitněte změny (`git commit -am 'Přidán scraper pro xyz'`)
4. Pushněte branch (`git push origin feature/novy-scraper`)
5. Vytvořte Pull Request

Viz [docs/adding-scrapers.md](docs/adding-scrapers.md) pro návod na přidání nového scraperu.

## Licence

MIT License - viz [LICENSE](LICENSE)
