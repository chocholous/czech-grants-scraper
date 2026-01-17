# Migration to Apify Actors

## Overview

This project has been migrated from a standalone Python scraper using `beautifulsoup4` and `playwright` to an **Apify Actor** using the Apify SDK and Crawlee framework.

## Key Changes

### 1. Architecture

**Before:**
- Standalone Python script (`scrapers/grants/dotaceeu.py`)
- Custom logging with Python `logging` module
- Manual file I/O for JSON/CSV output
- Direct Playwright usage for browser automation

**After:**
- Apify Actor with entry point at `src/main.py`
- Apify SDK (`apify`) for Actor lifecycle management
- Crawlee framework for web scraping
- `Actor.log` for secure logging (auto-censors credentials)
- `Actor.push_data()` for dataset storage
- `Actor.set_value()` for key-value store

### 2. Dependencies

**Removed:**
- `playwright` (standalone) → Now using `crawlee[playwright]`
- `requests` → Replaced with `httpx` for async support

**Added:**
- `apify>=2.0.0` - Apify SDK
- `crawlee[playwright]>=0.4.0` - Web scraping framework
- `httpx>=0.27.0` - Async HTTP client

### 3. File Structure

**New files:**
```
.actor/
├── actor.json              # Actor configuration
├── input_schema.json       # Input parameters UI
├── dataset_schema.json     # Output data structure
└── INPUT.json              # Local development input

src/
├── __init__.py
└── main.py                 # Actor entry point

Dockerfile                  # Apify runtime container
.dockerignore              # Docker build exclusions
```

**Modified files:**
- `pyproject.toml` - Updated dependencies
- `README.md` - Apify documentation
- `scrapers/grants/sources/base.py` - Actor.log compatibility
- `scrapers/grants/sources/utils.py` - Actor.log + httpx
- `scrapers/grants/sources/esfcr_cz.py` - Async HTTP

### 4. Scraping Strategy

**Before:**
- Single Playwright browser for everything
- Manual pagination logic
- Custom retry/recovery

**After:**
- `PlaywrightCrawler` for AJAX pagination (dotaceeu.cz listing)
- `BeautifulSoupCrawler` for detail pages (10x faster, no JS needed)
- Crawlee handles retries, concurrency, and request queue

### 5. Data Storage

**Before:**
```python
# Custom JSON/CSV files
storage.save_json(grants)
storage.save_csv(grants)
```

**After:**
```python
# Apify Dataset
await Actor.push_data(grant)

# Apify Key-Value Store (for documents)
await Actor.set_value(f"deep_{grant_id}", content)
```

### 6. Logging

**Before:**
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Message")
```

**After:**
```python
from apify import Actor
Actor.log.info("Message")  # Auto-censors API keys & credentials
```

### 7. Configuration

**Before:**
- `config.yml` file
- Command-line arguments
- Environment variables

**After:**
- Input schema (`.actor/input_schema.json`)
- Configured via Apify Console UI
- Still supports local `INPUT.json` for development

## Running the Actor

### Local Development

```bash
# Install dependencies
pip install -e .
playwright install chromium

# Run locally (uses .actor/INPUT.json)
apify run
```

### Deploy to Apify

```bash
# Login to Apify
apify login

# Deploy
apify push

# Run on Apify platform
# → Go to Apify Console and click "Start"
```

## Input Parameters

Configure in Apify Console or `.actor/INPUT.json`:

```json
{
  "scrapeMode": "basic",        // or "deep" for document extraction
  "maxGrants": 10,              // 0 = unlimited
  "ngoOnly": false,             // Filter NGO-eligible grants
  "sources": [],                // Empty = all sources
  "delays": {
    "pageNavigation": 3000,
    "loadMoreClick": 2000,
    "betweenItems": 500
  },
  "ngoKeywords": [
    "neziskov", "spolek", "nadace", ...
  ]
}
```

## Output

### Dataset
- Structured grant data (JSON)
- Accessible via Apify API
- Can export as JSON, CSV, Excel, HTML

### Key-Value Store (deep mode)
- `deep_{external_id}` - Full grant content
- Downloaded documents (PDF, XLSX, DOCX)
- Markdown conversions

## Benefits of Apify

1. **Cloud execution** - No need to run locally
2. **Scheduling** - Run daily/weekly automatically
3. **Monitoring** - Built-in logs, metrics, alerts
4. **Scaling** - Automatic resource management
5. **API access** - Programmatic data access
6. **Storage** - Managed datasets and key-value stores
7. **Security** - Automatic credential censoring in logs

## Backward Compatibility

The old `scrapers/grants/dotaceeu.py` script is preserved but deprecated. All sub-scrapers have been updated to work with both:
- Apify Actor environment (uses `Actor.log`, `httpx`)
- Standalone mode (falls back to `logging`, `requests`)

This is achieved via:
```python
try:
    from apify import Actor
    ACTOR_AVAILABLE = True
except ImportError:
    ACTOR_AVAILABLE = False
    import logging
```

## Migration Checklist

- [x] Create `.actor/` configuration
- [x] Update dependencies in `pyproject.toml`
- [x] Create Dockerfile
- [x] Create `src/main.py` entry point
- [x] Convert to Crawlee (PlaywrightCrawler + BeautifulSoupCrawler)
- [x] Replace logging with `Actor.log`
- [x] Replace storage with `Actor.push_data()` / `Actor.set_value()`
- [x] Update README with Apify instructions
- [x] Create input/output schemas
- [x] Test local run with `apify run`

## Next Steps

1. **Test locally:**
   ```bash
   apify run
   ```

2. **Deploy to Apify:**
   ```bash
   apify login
   apify push
   ```

3. **Configure scheduling** in Apify Console

4. **Set up monitoring** (email alerts, webhooks)

5. **Integrate with downstream systems** via Apify API

## Resources

- [Apify Documentation](https://docs.apify.com)
- [Crawlee Documentation](https://crawlee.dev)
- [Actor Specification](https://raw.githubusercontent.com/apify/actor-whitepaper/refs/heads/master/README.md)
- [AGENTS.md](./AGENTS.md) - Apify development guide
