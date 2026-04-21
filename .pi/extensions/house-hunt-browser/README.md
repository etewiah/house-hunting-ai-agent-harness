# house-hunt-browser Pi extension

Project-local Pi extension that adds browser/search-oriented tools for the `browser-house-hunt` skill.

## Tools

- `property_web_search` — search the web for property listing pages
- `property_listing_extract` — fetch and normalize a listing page into the harness listing shape
- `run_house_hunt_harness` — run the Python harness on normalized listings

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

## Notes

- Search currently uses DuckDuckGo HTML results and then filters to known property hosts.
- Extraction is heuristic and should be treated as a best-effort normalizer.
- Keep `source_url` for every listing and do not invent missing values.
