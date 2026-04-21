# Fixture tests

Inspired by `property_web_scraper`, this extension now includes lightweight HTML fixtures and extraction tests.

Run them with:

```bash
cd .pi/extensions/house-hunt-browser
node --test test/*.test.mjs
```

These fixtures are intentionally small and synthetic. They validate that the parser still understands key portal patterns:

- Rightmove via `window.PAGE_MODEL`
- Zoopla via `__NEXT_DATA__`
- OnTheMarket via `__NEXT_DATA__` with JSON-LD present

For future hardening, capture real rendered HTML from live listing pages and add more fixtures here.
