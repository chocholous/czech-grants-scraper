# AI-Enhanced Data Extraction

MZ Grants Scraper podporuje **AI-enhanced režim** pomocí Claude Haiku API pro extrakci strukturovaných dat z nestrukturovaného textu.

## Výhody AI Extraction

### Bez AI (MVP režim):
```json
{
  "eligibility": ["Není specifikováno"],
  "fundingAmount": {"min": 0, "max": 0, "currency": "CZK"},
  "status": "partial",
  "statusNotes": "Missing fields: eligibility, fundingAmount. Details available in PDF attachments."
}
```

### S AI enhancement:
```json
{
  "eligibility": [
    "nestátní neziskové organizace",
    "kraje",
    "obce",
    "zdravotnická zařízení"
  ],
  "fundingAmount": {"min": 50000, "max": 500000, "currency": "CZK"},
  "status": "ok",
  "statusNotes": "All mandatory fields present"
}
```

## Jak zapnout AI extraction

### 1. Nastavit Anthropic API klíč

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

Nebo v Apify platform: **Settings → Environment variables**

### 2. Spustit actora

Actor automaticky detekuje dostupnost API klíče:

```python
# Automatická detekce
if is_ai_extraction_available():
    # Použije AI pro extraction
else:
    # Použije regex fallback (MVP)
```

## Co AI extrahuje

AI-powered extrakce z textu stránky:

1. **Eligibility** - Seznam oprávněných žadatelů
2. **Funding amounts** - Min/max částky v Kč
3. **Deadline** - Přesný termín (pokud regex selže)
4. **Summary** - Stručné shrnutí účelu dotace

## Cena a rychlost

- **Model**: Claude 3.5 Haiku
- **Rychlost**: ~1-2s per grant
- **Cena**: ~$0.001 per grant (8000 tokens @ $0.25/1M input)
- **Celkem**: Pro 6 grantů ≈ $0.006 per run

## Fallback strategie

AI extraction je **optional enhancement**:

1. ✅ Regex extraction běží vždy (základní data)
2. ✅ AI se použije jen pokud je API key dostupný
3. ✅ Pokud AI selže, použijí se regex výsledky
4. ✅ Actor funguje i bez API klíče (MVP režim)

## Testování

### Test bez AI:
```bash
# Bez API key
apify run
```

### Test s AI:
```bash
# S API key
export ANTHROPIC_API_KEY="sk-ant-..."
apify run
```

Check logy pro:
```
INFO: Using AI extraction for enhanced data quality
INFO: AI extracted eligibility: 4 recipients
INFO: AI extracted funding: {'min': 50000, 'max': 500000, 'currency': 'CZK'}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (none) | Anthropic API key pro AI extraction |
| `HAIKU_MODEL` | `claude-3-5-haiku-20241022` | Model pro extraction |

## Troubleshooting

**"AI extraction failed"** v lozích:
- Zkontroluj API key: `echo $ANTHROPIC_API_KEY`
- Zkontroluj quota na console.anthropic.com
- Actor pokračuje s regex fallbackem

**Žádné AI logy**:
- API key není nastaven → běží MVP režim
- To je OK, actor funguje správně

**Token limit exceeded**:
- Extractor používá prvních 8000 znaků textu
- Pro velmi dlouhé stránky může být potřeba zvýšit limit
