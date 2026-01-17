# MZ Grants Scraper

Apify Actor pro scraping grantů z Ministerstva zdravotnictví ČR (MZ).

## Zdroj dat

- **URL**: https://mzd.gov.cz/category/dotace-a-programove-financovani/narodni-dotacni-programy-2026/
- **Počet programů**: ~6 dotačních programů
- **Struktura**: Kategorie → Programy → Detail stránky s dokumenty

## Módy spuštění

- **search**: Pouze dotazy na existující dataset (bez scrapingu)
- **refresh**: Vynucený scraping všech zdrojů
- **auto**: Automatický režim - scrape pouze pokud jsou data stará (staleAfterDays)

## Input parametry

```json
{
  "mode": "auto",
  "query": "HIV",
  "onlyActive": true,
  "staleAfterDays": 7,
  "limit": 100
}
```

## Output

Dataset s granty obsahující mandatory fields podle PRD:
- recordType, sourceId, sourceName, sourceUrl, grantUrl
- title, eligibility, fundingAmount, deadline
- status, statusNotes, extractedAt, contentHash

## Lokální vývoj

```bash
cd actors/mz-actor
pip install -r requirements.txt
apify run
```

## Deploy

```bash
apify login
apify push
```
