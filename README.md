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
