# LLM Enrichment

The scraper supports optional LLM-based extraction to enrich grant data with detailed eligibility criteria, evaluation criteria, and thematic keywords that are difficult to extract with traditional regex/CSS selectors.

## How It Works

1. **Traditional scraping** extracts structured data (documents, URLs, dates, amounts)
2. **LLM enrichment** (optional) analyzes the page text to extract:
   - Eligibility criteria (categorized by: applicant, project, financial, territorial, temporal)
   - Evaluation/scoring criteria
   - Supported vs unsupported activities
   - Required attachments
   - Thematic keywords for categorization

## Enabling LLM Enrichment

### In Actor Input

```json
{
  "enableLlm": true,
  "llmModel": "anthropic/claude-haiku-4.5"
}
```

### Input Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enableLlm` | boolean | `false` | Enable LLM extraction |
| `llmModel` | string | `anthropic/claude-haiku-4.5` | OpenRouter model to use |

### Available Models

| Model | Speed | Cost | Quality |
|-------|-------|------|---------|
| `anthropic/claude-sonnet-4.5` | Medium | $$ | Best for Czech legal text |
| `anthropic/claude-haiku-4.5` | Fast | $ | Good, much cheaper |
| `openai/gpt-5` | Medium | $$ | Comparable to Sonnet |
| `openai/gpt-5-mini` | Fast | $ | Budget option |
| `google/gemini-2.5-pro` | Medium | $$ | Alternative |

## Authentication

LLM enrichment uses the [Apify OpenRouter Actor](https://apify.com/apify/openrouter) which authenticates via your Apify token. No additional API keys needed when running on the Apify platform.

For local development, set the `APIFY_TOKEN` environment variable:

```bash
export APIFY_TOKEN="your-apify-token"
```

## Output Format

When LLM enrichment is enabled, grants include an `enhancedInfo` field:

```json
{
  "recordType": "grant",
  "sourceUrl": "https://opst.cz/dotace/101-vyzva/",
  "description": "...",
  "enhancedInfo": {
    "eligibility_criteria": [
      {
        "criterion": "Žadatelem může být pouze Karlovarský kraj",
        "category": "applicant",
        "is_mandatory": true
      },
      {
        "criterion": "Projekt musí být realizován v Karlovarském kraji",
        "category": "territorial",
        "is_mandatory": true
      }
    ],
    "evaluation_criteria": [
      {
        "criterion": "Soulad projektu s cíli Fondu",
        "max_points": null,
        "weight": null
      }
    ],
    "supported_activities": [
      "Poskytování voucherů pro rozvoj podnikání"
    ],
    "unsupported_activities": [],
    "territorial_restrictions": "Karlovarský kraj",
    "required_attachments": [
      "Souhrnný přehled počtu podaných žádostí",
      "Tabulka pro vyhodnocení programu"
    ],
    "thematic_keywords": [
      "spravedlivá transformace",
      "podpora podnikání",
      "vouchery"
    ]
  }
}
```

## Cost Considerations

LLM enrichment adds:
- **Time**: ~2-5 seconds per grant page
- **Cost**: ~$0.01-0.05 per grant (depends on model and page length)

For bulk scraping, consider:
1. Using a cheaper model like `claude-3-haiku` or `gpt-4o-mini`
2. Running without LLM first, then enriching selected grants
3. Setting `maxGrants` to limit scope during testing

## Programmatic Usage

When using scrapers directly in code:

```python
from scrapers.grants.sources.opst_cz import OPSTCzScraper

# With LLM enabled
scraper = OPSTCzScraper(enable_llm=True, llm_model="anthropic/claude-haiku-4.5")

# Extract with enrichment
content = await scraper.extract_content(url, metadata)

# Or override per-call
content = await scraper.extract_content(url, metadata, use_llm=True)
```

## Architecture

```
┌─────────────────────┐
│   Grant Page HTML   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Traditional Scraper │  ← CSS selectors, regex
│  (BeautifulSoup)    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   GrantContent      │  ← Documents, URLs, dates
└─────────┬───────────┘
          │ (if enableLlm)
          ▼
┌─────────────────────┐
│   LLM Extractor     │  ← pydantic-ai + OpenRouter
│  (EnhancedGrantData)│
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ GrantContent +      │
│ enhanced_info       │
└─────────────────────┘
```

The LLM extractor uses [pydantic-ai](https://ai.pydantic.dev/) for structured output enforcement, ensuring the LLM returns data matching the expected schema.
