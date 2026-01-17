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

> **Poznámka:** Kompletní výzkum zdrojů je k dispozici v adresáři `/docs/research/`:
> - `grant-sources-complete.md` - Kompletní přehled všech zdrojů
> - `zdroje-kompletni-seznam.md` - Seznam 300+ URL
> - `krajske-dotace-detail.md` - Detailní mapování krajů
> - `nadace-detail.md` - Detailní přehled nadací
> - `mezinarodni-zdroje-detail.md` - Mezinárodní zdroje

### Priorita 1 - Agregátory a vysoký objem

| Zdroj | URL | Popis |
|-------|-----|-------|
| Grantový diář | grantovydiar.cz | Kalendář výzev pro neziskovky |
| DotaceOnline | dotaceonline.cz | Monitoring všech výzev |
| Svět neziskovek | svetneziskovek.cz | Grantový diář s upozorněními |

### Priorita 2 - Ministerstva

| Zdroj | URL | Popis |
|-------|-----|-------|
| MŽP - Program NNO | mzp.gov.cz | 12 témat, 50-300 tis. Kč |
| MMR - Dotace NNO | mmr.gov.cz | Přístupnost, bydlení, regiony |
| MŠMT | msmt.gov.cz | Mládež, vzdělávání |

### Priorita 3 - Nadace

| Zdroj | URL | Popis | Objem |
|-------|-----|-------|-------|
| Nadace OSF | granty.nadaceosf.cz | Občanská společnost | 13+ mil. EUR |
| Nadace ČEZ | nadacecez.cz | Sociální služby | 270 mil. Kč/rok |
| Nadace Sirius | nadacesirius.cz | Ohrožené děti | 10+ mil. Kč |
| NROS | nros.cz | Pomozte dětem, Správný start | - |
| Nadace O2 | nadaceo2.cz | Digitální vzdělávání | 5 mil. Kč/rok |
| Světluška | svetluska.rozhlas.cz | Zrakově postižení | - |
| Nadace Partnerství | nadacepartnerstvi.cz | Ekologie, stromy | - |

### Priorita 4 - Kraje

| Zdroj | URL | Popis |
|-------|-----|-------|
| Praha | granty.praha.eu | Komplexní portál |
| Středočeský | dotace.kr-stredocesky.cz | EDP systém |
| Jihomoravský | dotace.kr-jihomoravsky.cz | Podpora NNO |
| Zlínský | zlinskykraj.cz/dotace | 21 programů, 191 mil. Kč |
| Moravskoslezský | msk.cz/temata/dotace | OPST region |

### Priorita 5 - Mezinárodní

| Zdroj | URL | Popis |
|-------|-----|-------|
| Visegrádský fond | visegradfund.org | V4 spolupráce |
| ERSTE Foundation | erstestiftung.org | Střední Evropa |
| Česko-německý fond | fondbudoucnosti.cz | Česko-německé projekty |
| Program LIFE | program-life.cz | EU - životní prostředí |

### Databáze a registry

| Zdroj | URL | Popis |
|-------|-----|-------|
| Veřejný rejstřík | justice.cz | Právní formy: nadace, nadační fond, spolek |
| ARES | ares.gov.cz | Administrativní registr ekonomických subjektů |
| CEDR | cedr.mfcr.cz | Centrální registr dotací |
| Fórum dárců | donorsforum.cz | TOP 100 nadací, Mapa dárcovství |

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
