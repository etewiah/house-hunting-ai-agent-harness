# Fixture tests

Inspired by `property_web_scraper`, this extension now includes lightweight HTML fixtures and extraction tests.

Run them with:

```bash
cd .pi/extensions/house-hunt-browser
node --test test/*.test.mjs
```

Fixture expectations now live in `manifest.mjs`, inspired by `property_web_scraper`'s manifest-driven fixture approach.

These fixtures are intentionally small and synthetic. They validate that the parser still understands key portal patterns:

- Rightmove via `window.PAGE_MODEL`
- Zoopla via `__NEXT_DATA__`
- OnTheMarket via `__NEXT_DATA__` with JSON-LD present

For future hardening, capture real rendered HTML from live listing pages and add more fixtures here.

When you add a new fixture:
1. save the HTML into `test/fixtures/`
2. add a manifest entry in `manifest.mjs`
3. run `npm test`

Current coverage includes variants for:
- Rightmove standard and minimal pages
- Zoopla standard and missing-bath pages
- OnTheMarket structured-data and text-fallback pages
