# Kompletní průzkum zdrojů grantů v České republice

Aktualizováno: 2026-01-17

## Statistiky nadačního sektoru ČR

- **3 236** nadací a nadačních fondů (2024)
- **571** nadací + **2 665** nadačních fondů
- **497** firemních nadačních subjektů
- **3,77 mld. Kč** rozděleno v roce 2023
- **TOP 10** nadací rozděluje téměř 48% celkového ročního objemu

---

## 1. MINISTERSTVA ČR

### Již implementované v projektu
| Ministerstvo | URL | Scraper |
|--------------|-----|---------|
| MV - Správa hranic | mv.gov.cz | `mv_gov_cz.py` |

### K implementaci

| Ministerstvo | URL | Portál dotací | Zaměření pro NNO |
|--------------|-----|---------------|------------------|
| **MŽP** | mzp.gov.cz | grantys.cz | Program NNO - 12 témat, 50-300 tis. Kč, max 70% |
| **MMR** | mmr.gov.cz | mmr.gov.cz/cs/narodni-dotace | Přístupnost staveb, bydlení, rozvoj regionů |
| **MŠMT** | msmt.gov.cz | msmt.gov.cz/mladez | Mládež, vzdělávání, sport |
| **MO** | mocr.mo.gov.cz | Jednotný dotační portál | Veteráni, branné aktivity |
| **HZS ČR** | hzscr.gov.cz | hzscr.gov.cz | Požární ochrana, IZS, krizové řízení |
| **MK** | mkcr.cz | - | Kultura, náboženské aktivity |
| **MPSV** | mpsv.cz | - | Sociální služby, zaměstnanost |
| **MZ** | mzcr.cz | - | Zdravotnictví, prevence |
| **Úřad vlády** | vlada.gov.cz | - | Mezioborové sítě NNO |

### Státní fondy a agentury

| Název | URL | Scraper | Zaměření |
|-------|-----|---------|----------|
| **SFŽP** | sfzp.cz | `sfzp_cz.py` | Modernizační fond, životní prostředí |
| **NRB** | nrb.cz | `nrb_cz.py` | Národní rozvojová banka |
| **NSA** | agenturasport.cz | - | Sport, tělovýchova |
| **GAČR** | gacr.cz | - | Základní výzkum (JUNIOR STAR až 25 mil. Kč) |
| **TAČR** | tacr.cz | - | Aplikovaný výzkum, program SIGMA |

---

## 2. EU OPERAČNÍ PROGRAMY 2021-2027

Celková alokace pro ČR: **21+ miliard EUR**

### Implementované
| Program | URL | Scraper | Zaměření |
|---------|-----|---------|----------|
| **OPST** | opst.cz | `opst_cz.py` | Spravedlivá transformace |
| **OP ŽP** | opzp.cz | `opzp_cz.py` | Životní prostředí |
| **ESF** | esfcr.cz | `esfcr_cz.py` | Evropský sociální fond |
| **OP TAK** | optak.gov.cz | `optak_gov_cz.py` | Technologie a konkurenceschopnost |
| **IROP** | irop.mmr.cz | `irop_mmr_cz.py` | Integrovaný regionální OP |

### K implementaci
| Program | Řídící orgán | Zaměření |
|---------|--------------|----------|
| **OP JAK** | MŠMT | Jan Amos Komenský - vzdělávání |
| **OP Zaměstnanost+** | MPSV | Zaměstnanost, sociální začleňování |
| **INTERREG** | různé | Přeshraniční spolupráce (SK, AT, DE, PL) |

---

## 3. KRAJE ČR - Detailní mapování

| Kraj | Hlavní portál | Alternativní URL | Poznámky |
|------|---------------|------------------|----------|
| **Praha** | granty.praha.eu | praha.eu/dotace-a-granty | Od 7.1.2025 pouze přes Identitu občana |
| **Středočeský** | dotace.kr-stredocesky.cz | stredoceskykraj.cz/web/dotace | EDP, kultura, sociální služby |
| **Jihočeský** | kraj-jihocesky.cz/cs/ku_dotace | - | Sport, kultura, mládež |
| **Plzeňský** | dotace.plzensky-kraj.cz | plzensky-kraj.cz/dotace-a-granty | Cestovní ruch, sport |
| **Karlovarský** | kr-karlovarsky.cz/dotace | dotace.kr-karlovarsky.cz | Strukturálně postižený region |
| **Ústecký** | kr-ustecky.cz/dotace-a-granty | - | Strukturálně postižený, OPST |
| **Liberecký** | dotace.kraj-lbc.cz | regionalni-rozvoj.kraj-lbc.cz | Kultura, sport |
| **Královéhradecký** | dotace.khk.cz | dotace.kr-kralovehradecky.cz | VVI podpora |
| **Pardubický** | dotace.pardubickykraj.cz | pardubickykraj.cz | Rodina, sociální podnikání |
| **Vysočina** | fondvysociny.cz | kr-vysocina.cz/granty-a-dotace | Fond Vysočiny |
| **Jihomoravský** | dotace.kr-jihomoravsky.cz | jmk.cz | Rodiny, NNO podpora |
| **Olomoucký** | olkraj.cz/dotace-granty-prispevky | - | RAP portál, kalendář dotací |
| **Zlínský** | zlinskykraj.cz/dotace | neziskovky.kr-zlinsky.cz | 21 programů, 191 mil. Kč |
| **Moravskoslezský** | msk.cz/temata/dotace | - | Strukturálně postižený, OPST |

---

## 4. PRAŽSKÉ MĚSTSKÉ ČÁSTI

| MČ | Oblasti | Portál | Poznámky |
|----|---------|--------|----------|
| **Praha 1** | Kultura 7 mil., sport 1,5 mil., památky | Grantys | |
| **Praha 4** | Sport, kultura, bezpečnost, sociální, ŽP | praha4.cz | 24+ mil. Kč 2025 |
| **Praha 6** | Kultura, sport, sociální, zdraví | praha6.cz/dotace | Šestka kulturní I. |
| **Praha 7** | Bezpečnost, kultura, sociální, sport | Grantys | |
| **Praha 10** | Kultura, sport, sociální, ŽP | praha10.cz/dotace | 24,1 mil. Kč 2025 |

---

## 5. ČESKÉ NADACE - Detailní přehled

### TOP nadace podle objemu

| Nadace | URL | Zaměření | Objem/rok | Programy |
|--------|-----|----------|-----------|----------|
| **DOBRÝ ANDĚL** | dobryandel.cz | Rodiny s nemocí | 396 mil. Kč | Přímá měsíční podpora |
| **Nadace ČEZ** | nadacecez.cz | Sociální služby | 270 mil. Kč | Stromy, hřiště, zaměstnanecké |
| **Nadace OSF** | osf.cz | Občanská společnost | ACF 13+ mil. EUR | granty.nadaceosf.cz |
| **Kellner Family** | kellnerfoundation.cz | Vzdělávání | 133 mil. Kč | Univerzity, Open Gate |
| **Nadace Kooperativy** | koop.cz/nadace | Senioři, zdraví | 1 mil. Kč ročně | Mezigenerační propojení |

### Nadace s aktivními grantovými výzvami

| Nadace | URL | Zaměření | Výše grantů | Termíny |
|--------|-----|----------|-------------|---------|
| **Nadace Partnerství** | nadacepartnerstvi.cz | Ekologie, stromy | až 140 tis. Kč | Sázíme budoucnost |
| **Nadace Sirius** | nadacesirius.cz | Ohrožené děti | 10+ mil. Kč | Raná péče, technologie |
| **Nadace O2** | nadaceo2.cz | Digitální vzdělávání | 30-100 tis. Kč | O2 Chytrá škola |
| **Nadace Neuron** | nadaceneuron.cz | Věda | až 1 mil. Kč | Expedice Neuron |
| **Světluška (ČRo)** | svetluska.rozhlas.cz | Zrakově postižení | - | HGŘ 2025 |
| **NROS** | nros.cz | Občanská společnost | - | Pomozte dětem, Správný start |
| **Divoké husy** | divokehusy.cz | Sociální, zdravotní | až 60 tis. Kč | Benefice |

### Firemní nadace

| Nadace | Zakladatel | Zaměření | Programy |
|--------|------------|----------|----------|
| **Nadace Vodafone** | Vodafone | Technologie pro společnost | Laboratoř (ne Rok jinak) |
| **Nadace KB** | Komerční banka | NNO obecně | 25 let působení |
| **Nadace České spořitelny** | ČS | Komunitní rozvoj | Dokážeme víc (s Via) |

### Rodinné nadace a filantropové

| Nadace | Zakladatel | Zaměření | Poznámky |
|--------|------------|----------|----------|
| **Nadace RSJ** | 10 akcionářů RSJ | Nadané děti, duševní zdraví | 150+ mil. Kč celkem |
| **Nadace Neuron** | Karel Janeček | Věda | 145+ mil. Kč investováno |
| **Bakala Foundation** | Zdeněk Bakala | Stipendia | Zahraniční univerzity |
| **Abakus** | Zakladatelé Avastu | Konec života, vzdělávání | Paliativní péče |
| **Nadace rodiny Vlčkových** | Vlčkovi | Těžce nemocné děti | 1,5 mld. Kč |

### Charitativní organizace

| Organizace | URL | Zaměření |
|------------|-----|----------|
| **Nadace Charty 77** | kontobariery.cz | Konto Bariéry - zdravotně postižení |
| **Charita ČR** | charita.cz | 274 lokálních charit |
| **Diakonie ČCE** | diakonie.cz | Sociální služby |

---

## 6. MEZINÁRODNÍ ZDROJE

### Visegrádský fond
- **Alokace:** 110+ mil. EUR za 21 let
- **Termíny:** 1.2., 1.6., 1.10.
- **Programy:** Visegrádské granty (min. 3 země V4), Visegrad+, Strategické granty (až 40 000 EUR)
- **URL:** visegradfund.org

### ERSTE Foundation (Rakousko)
- **Zaměření:** Střední a jihovýchodní Evropa
- **Podpořeno:** 2 200+ projektů, 148+ mil. EUR
- **Programy:** Kontakt (umění), Media Forward Fund
- **URL:** apply.erstestiftung.org

### Česko-německý fond budoucnosti
- **Alokace 2025-2026:** 7 mil. Kč (Frankfurtský knižní veletrh)
- **Podpora:** až 50% (70% u tématu roku)
- **Termíny:** konec každého čtvrtletí
- **URL:** fondbudoucnosti.cz

### EEA & Norway Grants (4. období)
- **Podepsáno:** 4.11.2025
- **Alokace pro ČR:** 5,5 mld. Kč
- **Fond pro občanskou společnost:** 20,3 mil. EUR
- **První výzvy:** přelom 2026/2027
- **URL:** eeagrants.cz

### EU programy (přímo z Bruselu)

| Program | Správce v ČR | Zaměření | Termíny 2025 |
|---------|--------------|----------|--------------|
| **Erasmus+** | DZS (dzs.cz) | Vzdělávání, mládež | Limit 25 nových akreditací |
| **LIFE** | MŽP | Životní prostředí | Národní výzva 100 mil. Kč |
| **Evropský sbor solidarity** | DZS | Dobrovolnictví | 18.2., 1.10. |
| **AKTION** | DZS | Česko-rakouská spolupráce | 29.4.2025 |
| **CEEPUS** | DZS | Střední Evropa | Kontinuální |

### Ambasády

| Ambasáda | Program | Částky | URL |
|----------|---------|--------|-----|
| **USA** | Program malých grantů | $3,000-$20,000 | - |
| **Německo** | DAAD, DFG spolupráce | - | prag.diplo.de |
| **Francie** | Institut français | Rezidence | - |

---

## 7. UNIVERZITNÍ GRANTY A STIPENDIA

### Grantové agentury

| Agentura | URL | Programy | Výše |
|----------|-----|----------|------|
| **GAČR** | gacr.cz | JUNIOR STAR, standardní | až 25 mil. Kč |
| **TAČR** | tacr.cz | SIGMA, Delta, Epsilon | různé |
| **GA UK** | cuni.cz/UK-9291 | Interní granty UK | - |

### Stipendia

- **MŠMT:** 1,91 mld. Kč na doktorandy (2025)
- **ČVUT:** Fond studentských projektů, až 12 000 Kč/měsíc
- **BTHA:** 12-13 000 Kč/měsíc (termín 29.4.2025)
- **Erasmus+:** 540-660 EUR/měsíc podle země

---

## 8. AGREGÁTORY A DATABÁZE

### Oficiální státní
| Zdroj | URL | Popis |
|-------|-----|-------|
| **DotaceEU.cz** | dotaceeu.cz | Oficiální portál EU fondů |
| **IS ReD (CEDR)** | cedr.mfcr.cz | Centrální evidence dotací |
| **Jednotný dotační portál** | isprofin.mfcr.cz | RISPF - všechna ministerstva |

### Soukromé/neziskové
| Zdroj | URL | Popis |
|-------|-----|-------|
| **Grantový diář** | grantovydiar.cz | Kalendář výzev pro neziskovky |
| **Svět neziskovek** | svetneziskovek.cz | Grantový diář s upozorněními |
| **DotaceOnline** | dotaceonline.cz | Monitoring všech výzev |
| **Grantika** | grantika.cz | Poradenství, přehledy |
| **Dotacni.info** | dotacni.info | Přehled aktuálních výzev |
| **Fórum dárců** | donorsforum.cz | TOP 100, Mapa dárcovství |

---

## 9. TECHNICKÉ POZNÁMKY PRO SCRAPER

### Systémy pro podávání žádostí

| Systém | Používá | Poznámky |
|--------|---------|----------|
| **Grantys** | MŽP, Praha 1, Praha 7, Nadace Partnerství | Společný systém |
| **RAP** | Olomoucký kraj | Portál komunikace pro občany |
| **Identita občana** | Liberecký kraj (od 7.1.2025) | eGovernment |
| **Jednotný dotační portál** | HZS, MO, další ministerstva | RISPF |

### Doporučení pro implementaci

**Priorita 1 - Vysoký objem, strukturovaná data:**
1. DotaceEU.cz - centrální výzvy EU (Playwright)
2. grantovydiar.cz - agregátor
3. granty.nadaceosf.cz
4. nadacecez.cz

**Priorita 2 - Ministerstva:**
5. MŽP - Program NNO (Grantys)
6. MMR - Dotace NNO
7. MŠMT - Granty vzdělávání

**Priorita 3 - Kraje:**
8. granty.praha.eu
9. dotace.kr-stredocesky.cz
10. dotace.kr-jihomoravsky.cz

**Priorita 4 - Nadace:**
11. nadacepartnerstvi.cz
12. nadacesirius.cz
13. nadaceo2.cz/granty
14. nros.cz

---

## 10. ZDROJE PRŮZKUMU

### Oficiální portály
- [Fórum dárců - TOP 100](https://www.donorsforum.cz/aktuality/zebricky-pruzkumy/top-100-nadaci-a-fondu.html)
- [Mapa dárcovství 2025](https://www.donorsforum.cz/mapa-darcovstvi/mapa-darcovstvi-2025.html)
- [MŽP Program NNO](https://mzp.gov.cz/cz/agenda/prehled-dotaci/program-na-podporu-projektu-nno/)
- [MMR Dotace NNO](https://mmr.gov.cz/cs/narodni-dotace/dotace-pro-nestatni-neziskove-organizace/)
- [DZS Erasmus+](https://www.dzs.cz/program/erasmus/projekty-granty)
- [Program LIFE](https://www.program-life.cz/)

### Nadace
- [Nadace OSF](https://osf.cz/en/grants/)
- [Nadace ČEZ](https://www.nadacecez.cz/cs/vyhlasovana-grantova-rizeni)
- [Nadace Sirius](https://www.nadacesirius.cz/granty/grantove-vyzvy)
- [Nadace O2](https://nadaceo2.cz/granty)
- [NROS](https://www.nros.cz/grantovy-harmonogram/)
- [Světluška](https://svetluska.rozhlas.cz/grantove-rizeni-pro-organizace-8099651)
- [Kellner Family Foundation](https://www.kellnerfoundation.cz/)

### Mezinárodní
- [Visegrádský fond](https://www.visegradfund.org/)
- [ERSTE Foundation](https://www.erstestiftung.org/en/)
- [Česko-německý fond budoucnosti](https://www.fondbudoucnosti.cz/)
- [EEA Grants ČR](https://www.eeagrants.cz/)

---

*Dokument vytvořen na základě webového průzkumu v lednu 2026.*
