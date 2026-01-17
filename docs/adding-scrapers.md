# Jak přidat nový scraper

## Rychlý start

### 1. Vytvořte nový soubor

```bash
touch scrapers/grants/sources/nazev_zdroje_cz.py
```

### 2. Implementujte scraper

```python
"""
Scraper pro [název zdroje]
URL: https://example.cz
"""

from .base import BaseScraper
from .models import Grant
from .registry import register_scraper


@register_scraper("nazev_zdroje_cz")
class NazevZdrojeScraper(BaseScraper):
    """Scraper pro [popis zdroje]."""

    BASE_URL = "https://example.cz"

    async def scrape(self) -> list[Grant]:
        """Hlavní metoda pro sběr grantů."""
        grants = []

        # 1. Získej seznam grantů
        response = await self.fetch(f"{self.BASE_URL}/grants")

        # 2. Parsuj jednotlivé granty
        for item in self.parse_list(response):
            grant = await self.parse_grant(item)
            if grant:
                grants.append(grant)

        return grants

    async def parse_grant(self, data: dict) -> Grant | None:
        """Parsuj jeden grant."""
        try:
            return Grant(
                title=data.get("title"),
                source=self.BASE_URL,
                amount_min=data.get("amount_min"),
                amount_max=data.get("amount_max"),
                deadline=data.get("deadline"),
                description=data.get("description"),
                url=data.get("url"),
            )
        except Exception as e:
            self.logger.error(f"Chyba při parsování: {e}")
            return None
```

### 3. Přidejte do konfigurace

```yaml
# config.yml
sources:
  - name: nazev_zdroje_cz
    enabled: true
```

### 4. Exportujte v `__init__.py`

```python
# scrapers/grants/sources/__init__.py
from .nazev_zdroje_cz import NazevZdrojeScraper
```

## Best practices

### Robustní parsování

```python
# Používejte safe gettery
title = data.get("title", "").strip() or None

# Validujte data
if not title:
    return None
```

### Rate limiting

```python
# Respektujte servery
await asyncio.sleep(1)  # Mezi requesty
```

### Error handling

```python
try:
    response = await self.fetch(url)
except Exception as e:
    self.logger.warning(f"Nelze načíst {url}: {e}")
    return []
```

### Logging

```python
self.logger.info(f"Nalezeno {len(grants)} grantů")
self.logger.debug(f"Parsování: {url}")
self.logger.error(f"Chyba: {e}")
```

## Testování

```bash
# Spusť testy pro nový scraper
pytest tests/test_scrapers.py -k "nazev_zdroje"

# Manuální test
python -c "
from scrapers.grants.sources.nazev_zdroje_cz import NazevZdrojeScraper
import asyncio

async def test():
    scraper = NazevZdrojeScraper()
    grants = await scraper.scrape()
    print(f'Nalezeno: {len(grants)} grantů')

asyncio.run(test())
"
```

## Checklist před PR

- [ ] Scraper má dokumentační docstring
- [ ] Implementuje `scrape()` metodu
- [ ] Registrován v registry
- [ ] Přidán do `__init__.py`
- [ ] Přidán do `config.yml`
- [ ] Funguje základní test
- [ ] Respektuje rate limiting
- [ ] Loguje důležité události
