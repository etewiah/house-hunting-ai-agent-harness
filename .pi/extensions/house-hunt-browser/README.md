# house-hunt-browser Pi extension

Project-local Pi extension that adds browser/search-oriented tools for the `browser-house-hunt` skill.

## Tools

- `property_web_search` — search the web for property listing pages
- `property_listing_extract` — fetch and normalize a listing page into the harness listing shape, with extraction diagnostics
- `extract_property_listings` — normalize multiple listing URLs in one call, with extraction diagnostics
- `run_house_hunt_harness` — run the Python harness on normalized listings
- `house_hunt_from_web` — end-to-end search + extract + rank in one tool

## Usage

Start pi in this repo, then run:

```bash
/reload
```

Pi should auto-discover this extension from `.pi/extensions/house-hunt-browser/`.

Then use the project skill:

```bash
/skill:browser-house-hunt
```

Or run the built-in smoke test command:

```bash
/house-hunt-smoke 2-bed flat near Birmingham New Street, under £250k, parking preferred
```

## Tests

```bash
cd .pi/extensions/house-hunt-browser
npm test
npm run validate-fixtures
npm run test:fixtures
```

## Capture a fixture

Inspired by `property_web_scraper`, you can capture or save HTML fixtures for parser work:

```bash
cd .pi/extensions/house-hunt-browser
npm run capture-fixture -- https://www.rightmove.co.uk/properties/123456789
npm run capture-fixture -- --file saved-page.html --url https://www.zoopla.co.uk/for-sale/details/42/
cat rendered.html | npm run capture-fixture -- --stdin --url https://www.onthemarket.com/details/7/
```

This saves the HTML under `test/fixtures/` and prints a suggested manifest entry for `test/manifest.mjs`.

## Notes

- Search currently uses DuckDuckGo HTML results and then filters to known property hosts.
- Extraction now includes site-specific parsers for Rightmove, Zoopla, and OnTheMarket, with generic fallback parsing.
- Extraction tool details include diagnostics such as parser used, host, whether JSON-LD was present, field source hints, and field-level provenance.
- Field provenance is now more precise, distinguishing sources like `json_ld`, `meta_description`, `title_tag`, `text_regex`, and `canonical_link`.
- Diagnostics also include an extraction `qualityScore`, `missingFields`, and human-readable `warnings`.
- Search, extraction, and harness runs also write JSON trace files under `.tmp/` for debugging.
- There is now a small fixture-based test suite inspired by `property_web_scraper` under `test/`.
- Extraction is still heuristic and should be treated as a best-effort normalizer.
- Keep `source_url` for every listing and do not invent missing values.
