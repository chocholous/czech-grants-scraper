# PRD: Apify Actor - Czech Grants & Charitable Causes

## Goal
Build a single Apify Actor that scrapes Czech grant announcements and supported charitable causes from a configurable list of sources (ministries, regions, cities, foundations), normalizes them into structured records, and stores them in a shared dataset. The Actor also serves search queries over the stored dataset and refreshes stale data on a weekly cadence.

## Users & Primary Use Cases
- Analysts searching for active grants or charitable programs by keywords, category, region, or eligibility.
- Operators refreshing or expanding the dataset with new sources.

## Actor Overview (Apify)
- **Single Actor** with two modes:
  - **Search-only**: query the existing dataset without scraping unless data is stale.
  - **Refresh**: scrape all sources and update dataset.
- **Storage**: Apify Dataset shared across runs (named dataset, e.g., `czech-grants`), plus Key-Value Store for metadata (last crawl timestamp per source).
- **Output**: Dataset items for grants and charitable causes, plus run output summary.

## Data Sources
- Configurable list of source URLs (ministries, regions, cities, foundations). Each source may require a specific scraper strategy (HTML, PDF, mixed).
- Source list will be provided later; architecture must support heterogeneous scrapers.

## Input Schema (Actor Input)
```json
{
  "query": "string (keywords)",
  "categories": ["string"],
  "regions": ["string"],
  "eligibility": ["string"],
  "fundingRange": {"min": 0, "max": 0},
  "deadlineRange": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "onlyActive": true,
  "mode": "search|refresh|auto",
  "staleAfterDays": 7,
  "limit": 100
}
```

Notes:
- `mode=auto` runs search first and triggers refresh for sources stale beyond `staleAfterDays`.

## Output Schema (Dataset Items)
### Grant Announcement
```json
{
  "recordType": "grant",
  "sourceId": "string",
  "sourceName": "string",
  "sourceUrl": "string",
  "grantUrl": "string",
  "title": "string",
  "summary": "string",
  "description": "string",
  "criteria": ["string"],
  "conditions": ["string"],
  "contact_email": ["string"],
  "contact_phone": ["string"],
  "eligibility": ["string"],
  "fundingAmount": {"min": 0, "max": 0, "currency": "CZK"},
  "deadline": "YYYY-MM-DD",
  "applicationWindow": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "regions": ["string"],
  "categories": ["string"],
  "attachments": [{"title": "string", "url": "string", "type": "pdf|doc|html"}],
  "language": "cs",
  "status": "ok|partial|error",
  "statusNotes": "string",
  "extractedAt": "YYYY-MM-DDTHH:MM:SSZ",
  "contentHash": "string"
}
```
#### Mandatory fields:
```json
{
  "recordType": "grant",
  "sourceId": "string",
  "sourceName": "string",
  "sourceUrl": "string",
  "grantUrl": "string",
  "title": "string",
  "eligibility": ["string"],
  "fundingAmount": {"min": 0, "max": 0, "currency": "CZK"},
  "deadline": "YYYY-MM-DD",
  "status": "ok|partial|error",
  "statusNotes": "string",
  "extractedAt": "YYYY-MM-DDTHH:MM:SSZ",
  "contentHash": "string"
}
```


### Charitable Cause
```json
{
  "recordType": "cause",
  "sourceId": "string",
  "sourceName": "string",
  "sourceUrl": "string",
  "causeUrl": "string",
  "title": "string",
  "summary": "string",
  "description": "string",
  "supportedActivities": ["string"],
  "eligibility": ["string"],
  "fundingAmount": {"min": 0, "max": 0, "currency": "CZK"},
  "regions": ["string"],
  "categories": ["string"],
  "attachments": [{"title": "string", "url": "string", "type": "pdf|doc|html"}],
  "language": "cs",
  "status": "ok|partial|error",
  "statusNotes": "string",
  "extractedAt": "YYYY-MM-DDTHH:MM:SSZ",
  "contentHash": "string"
}
```

## Parsing & Normalization
- Always run unstructured content through a structured extraction pipeline (e.g., pydantic-ai) to fill the schema.
- Preserve raw text and URLs for traceability; store key metadata for filtering.
- `status` indicates parse quality; `partial` is acceptable and must be stored.

## Storage & Deduplication
- Use a **named dataset** (e.g., `czech-grants`) so data persists across invocations.
- Use `contentHash` (hash of title + URL + key fields) for deduplication.
- Store per-source `lastFetchedAt` in Key-Value Store to support staleness checks.

## Refresh Logic
- Weekly default refresh (`staleAfterDays=7`).
- `auto` mode: if a source is stale, refresh it before returning search results for that source.

## Error Handling & Observability
- Log per-source scrape status and counts (new/updated/skipped/errors).
- For errors, store a dataset item with `status=error` and `statusNotes`.

## Non-Goals (for now)
- Full-text search engine integration.
- Multi-language output (fields are English keys with Czech content).
- Real-time notifications.

## Open Questions
- Final source list and source-specific scraping strategies.
- Category and region taxonomies (define allowed values).
- Criteria for “active” grants (deadline vs. status text).
- Required output fields per client use case.
