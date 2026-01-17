# Czech EU Grants Data Access: dotaceeu.cz Analysis

**No public API exists for Czech EU grant calls**, but a combination of RSS feeds for monitoring and HTML scraping for detail extraction offers the most reliable approach. The official portal dotaceeu.cz provides server-rendered content, predictable URL patterns, and minimal anti-scraping measures, making it technically accessible. However, the critical gap across all Czech and EU data sources is that **machine-readable grant CALLS (výzvy) with deadlines simply don't exist**—only funded project data is available in bulk formats.

## Official data sources: RSS feeds are your best option

### dotaceeu.cz native feeds and exports

The portal offers an **extensive RSS feed system** at `https://www.dotaceeu.cz/cs/ostatni/web/rss` with dedicated feeds for different content types:

| Feed | URL | Purpose |
|------|-----|---------|
| **Grant Calls (Výzvy)** | `?rss=Vyzvy` | Primary feed for new/updated calls |
| 2021-2027 Period | `?rss=2021-2027` | Current programming period |
| 2014-2020 Period | `?rss=2014-2020` | Previous period calls |
| News (Novinky) | `?rss=Novinky` | Portal announcements |
| Events (Akce) | `?rss=Akce` | Seminars, conferences |

The RSS feeds provide basic metadata and direct links to detail pages, making them ideal for **monitoring new calls without scraping**. For bulk project/beneficiary data, monthly **XLSX exports** (8-15MB files) are available at `/cs/statistiky-a-analyzy/seznam-operaci-(prijemcu)`, updated by the 15th of each month. These contain project names, operational programmes, beneficiary details, IČO (company ID), and support amounts—but critically, **not active call information**.

### Czech government open data limitations

The **IS ReD registry** (data.mf.gov.cz) provides comprehensive CSV exports of all Czech subsidies since 1999, but covers awarded grants, not open calls. The **Hlídač státu API** (api.hlidacstatu.cz) aggregates 4+ million subsidy records from IS ReD, CEDR, EU funds, SZIF, and regional grants with good documentation and free access—but again, only historical/awarded data. The Czech National Open Data Catalog (data.gov.cz) contains no comprehensive grant calls dataset; EU funds data available there describes funded projects, not funding opportunities.

### EU-level databases don't include Czech national OPs

The **EU Funding & Tenders Portal** provides APIs and RSS feeds for direct EU programmes (Horizon Europe, Digital Europe, LIFE), but explicitly **excludes Czech national operational programmes** like IROP, OPZ+, or OP TAK. **Kohesio** (kohesio.ec.europa.eu) offers excellent SPARQL/CSV/RDF access to 1.5+ million funded projects including Czech ones, but contains zero active call data. No third-party aggregator offers a Czech grant calls API—services like Dotace.eu and Dotační Noviny provide human-readable aggregation without programmatic access.

## Site structure analysis: scraping-friendly architecture

### Technology stack and rendering

dotaceeu.cz runs on **Kentico CMS** (Czech-made, ASP.NET/SQL Server based), evidenced by `/CMSPages/GetResource.ashx` endpoints and `__doPostBack` patterns. Content is **server-rendered**—all grant call data loads in initial HTML without JavaScript SPA complications. Anti-scraping measures are minimal: no CAPTCHA, no visible rate limiting, standard cookie consent. The main challenges are ASP.NET PostBack forms for pagination and Czech date formats requiring parsing.

### URL structure patterns

Grant calls follow predictable hierarchical paths:

```
2021-2027 Period:
/cs/jak-ziskat-dotaci/vyzvy/obdobi-2021-2027/[OP-CODE]/[CALL-SLUG]

Example:
/obdobi-2021-2027/06-integrovany-regionalni-operacni-program/36-vyzva-irop-infrastruktura-pro-cyklistickou-dopr
```

Filtering uses query parameters: `?Program=[Program Name]&Obdobi=20212027`. Documents are stored at `/Dotace/media/SF/[Path]/[Filename].pdf` and `/getmedia/[GUID]/[Filename].xlsx.aspx?ext=.xlsx`.

### Grant call page structure and extractable fields

Each call detail page contains a **structured info table** with consistent fields:

| Field (Czech) | Field (English) | Scraping Target |
|---------------|-----------------|-----------------|
| Číslo výzvy | Call number | Unique identifier |
| Druh výzvy | Call type | Průběžná/Kolová |
| Oprávnění žadatelé | **Eligible applicants** | NGO filtering possible |
| Zahájení příjmu žádostí | Application start | Date field |
| Ukončení příjmu žádostí | **Submission deadline** | Critical date field |
| Stav výzvy | Call status | Open/Closed/Planned |
| Operační program | Operational programme | Programme classification |

Page sections include: info table → detailed description → status change history (Aktuality) → **attached documents** (Připojené dokumenty with PDFs) → social sharing. Funding amounts (min/max) appear in the detailed description text or attached PDF documents, not in the structured table—requiring either text parsing or PDF extraction.

## Recommended technical approach

### Primary strategy: RSS + detail scraping hybrid

**Step 1: Monitor RSS feed** (`?rss=Vyzvy`) for new/updated calls. This returns XML with call titles and detail page URLs without any scraping burden.

**Step 2: Fetch individual detail pages** from RSS links and parse the HTML info table for structured metadata. The table uses `<table>` markup with consistent row patterns.

**Step 3: Extract attached documents** by parsing the "Připojené dokumenty" section for PDF/DOCX links, particularly for detailed eligibility criteria and funding amounts.

**Step 4: For comprehensive listing** (beyond RSS), handle pagination on `/cs/jak-ziskat-dotaci/vyzvy` using ASP.NET ViewState management for the "Načíst další" (Load more) PostBack button.

### NGO eligibility filtering

The "Oprávnění žadatelé" field contains text like "nestátní neziskové organizace," "spolky," "obecně prospěšné společnosti," or "NNO." Build a keyword filter matching: `neziskov`, `spolek`, `nadace`, `církevní`, `NNO`, `obecně prospěšn` to identify NGO-eligible calls. Some calls specify exclusions, so parse for negative patterns too.

### Data field extraction mapping

| Required Field | Source Location | Extraction Method |
|----------------|-----------------|-------------------|
| Deadline | Info table: "Ukončení příjmu" | HTML table parse, date regex |
| Grant amounts | Description text or PDF | Text search for "Kč", PDF extraction |
| Eligibility | Info table: "Oprávnění žadatelé" | HTML table parse |
| Application link | Info table: "Více informací" | Anchor tag href |
| Programme name | Info table: "Operační program" | HTML table parse |
| Documents | "Připojené dokumenty" section | Parse href for `/Dotace/media/` |

### Technical implementation notes

For scraping, use standard HTTP clients with cookie handling (ASP.NET sessions). Date parsing must handle Czech format "11. 10. 2022" → ISO date. The sitemap at `/cs/ostatni/web/mapa-webu` provides section navigation but no comprehensive call listing. Robots.txt doesn't explicitly block scraping. Consider **10-30 second delays** between requests for politeness despite no visible rate limiting.

## Key limitations and gaps

**Funding amounts** are inconsistently structured—sometimes in description text ("alokace 500 mil. Kč"), sometimes only in attached PDF documents. Full extraction requires PDF text parsing. **Eligibility criteria** in the info table are often abbreviated; detailed requirements are in attached documentation. **Historical calls** (closed) remain accessible but pagination for complete archives requires PostBack handling. No single source—Czech or EU level—provides this data in a clean API format; the RSS+scraping approach represents the most reliable path for comprehensive coverage.

## Summary of data sources

| Source | Grant Calls? | Format | Best Use |
|--------|--------------|--------|----------|
| dotaceeu.cz RSS | ✅ Yes | XML | Primary monitoring |
| dotaceeu.cz pages | ✅ Yes | HTML | Detail extraction |
| dotaceeu.cz XLSX | ❌ Projects only | Excel | Beneficiary analysis |
| Hlídač státu API | ❌ Awarded only | JSON | Historical analysis |
| IS ReD (data.mf.gov.cz) | ❌ Awarded only | CSV | Official records |
| EU F&T Portal | ✅ EU direct only | RSS/API | Horizon, LIFE, etc. |
| Kohesio | ❌ Projects only | SPARQL/CSV | Funded project research |

For Czech operational programme grant calls, **RSS feeds + HTML scraping of dotaceeu.cz remains the only viable approach** until official APIs are developed.