# Přehled zdrojů dat

## Implementované zdroje

### Grantové programy

#### OP Spravedlivá transformace (opst.cz)
- **URL:** https://opst.cz
- **Typ:** Operační program EU
- **Zaměření:** Uhelné regiony, dekarbonizace
- **Scraper:** `opst_cz.py`

#### MV - Správa hranic (mv.gov.cz)
- **URL:** https://www.mv.gov.cz
- **Typ:** Operační program EU
- **Zaměření:** Hranice, vízová politika, Schengen
- **Scraper:** `mv_gov_cz.py`

#### OP Životní prostředí (opzp.cz)
- **URL:** https://opzp.cz
- **Typ:** Operační program EU
- **Zaměření:** Životní prostředí, klima
- **Scraper:** `opzp_cz.py`

#### Národní rozvojová banka (nrb.cz)
- **URL:** https://nrb.cz
- **Typ:** Státní banka
- **Zaměření:** Úvěry, záruky, podpora podnikání
- **Scraper:** `nrb_cz.py`

#### ESF - Zaměstnanost (esfcr.cz)
- **URL:** https://esfcr.cz
- **Typ:** Evropský sociální fond
- **Zaměření:** Zaměstnanost, vzdělávání, sociální inkluze
- **Scraper:** `esfcr_cz.py`

#### OP TAK (optak.gov.cz)
- **URL:** https://optak.gov.cz
- **Typ:** Operační program EU
- **Zaměření:** Technologie, inovace, konkurenceschopnost
- **Scraper:** `optak_gov_cz.py`

#### SFŽP - Modernizační fond (sfzp.cz)
- **URL:** https://sfzp.cz
- **Typ:** Státní fond
- **Zaměření:** Životní prostředí, energetika, modernizace
- **Scraper:** `sfzp_cz.py`

#### IROP (irop.mmr.cz)
- **URL:** https://irop.mmr.cz
- **Typ:** Operační program EU
- **Zaměření:** Regionální rozvoj, infrastruktura
- **Scraper:** `irop_mmr_cz.py`

## Plánované zdroje

### Charitativní organizace

| Zdroj | URL | Popis |
|-------|-----|-------|
| Veřejný rejstřík | justice.cz | Právní formy: nadace, nadační fond, spolek |
| ARES | ares.gov.cz | Administrativní registr ekonomických subjektů |
| CEDR | cedr.mfcr.cz | Centrální registr dotací |
| Neziskovky.cz | neziskovky.cz | Databáze neziskových organizací |

### Nadace

| Zdroj | URL | Popis |
|-------|-----|-------|
| Nadace OSF | osf.cz | Open Society Fund Praha |
| Nadace Via | nadacevia.cz | Podpora komunitního rozvoje |
| Nadace Partnerství | nadacepartnerstvi.cz | Ekologické projekty |
| Kellner Family Foundation | kellnerfoundation.cz | Vzdělávání |

## Datový formát

Každý grant obsahuje:

```json
{
  "title": "Název grantu",
  "source": "https://example.cz",
  "source_name": "Název zdroje",
  "amount_min": 100000,
  "amount_max": 1000000,
  "currency": "CZK",
  "deadline": "2025-03-31",
  "description": "Popis grantu...",
  "url": "https://example.cz/grant/123",
  "eligibility": ["MSP", "velké podniky"],
  "regions": ["Moravskoslezský", "Ústecký"],
  "categories": ["životní prostředí", "energie"],
  "scraped_at": "2025-01-17T10:00:00Z"
}
```
