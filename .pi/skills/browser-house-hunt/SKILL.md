---
name: browser-house-hunt
description: Find property listings with browser/search/API tools, normalize them into Listing-shaped dicts, and run this repo's full house-hunting harness pipeline. Use when a user wants real candidate properties ranked against a buyer brief.
metadata:
  tags: house-hunt, browser, listings, ranking, property
---

# Browser House Hunt

Use this skill when the user wants help finding actual properties to buy or rent and you have browser, search, scraping, API, or page-reading tools available.

If the project-local Pi extension `house-hunt-browser` is loaded, prefer its tools:
- `house_hunt_from_web` for end-to-end runs
- `property_web_search`
- `property_listing_extract`
- `extract_property_listings`
- `run_house_hunt_harness`

This skill treats **web discovery** and **harness evaluation** as separate steps:
1. collect candidate listings from Rightmove / Zoopla / platform APIs / browser results
2. normalize each listing into the repo's `Listing` shape
3. run the harness pipeline using those supplied listings
4. report ranked matches, explanations, comparison, affordability, and next steps
5. publish to HomesToCompare only when the selected listings have verified photos

When the extension is available, the fastest path is usually:
1. call `house_hunt_from_web`
2. if results are weak, fall back to `property_web_search` + `extract_property_listings` + `run_house_hunt_harness`

If browser/search tools are **not** available, tell the user you can still run the harness if they paste listing URLs or listing data.

## Listing schema to normalize into

Each candidate listing should become a JSON object with these fields:

```json
{
  "id": "unique-id-or-url-slug",
  "title": "Listing title",
  "price": 235000,
  "bedrooms": 2,
  "bathrooms": 1,
  "location": "Birmingham",
  "commute_minutes": 15,
  "features": ["parking", "garden"],
  "description": "Short summary of the listing",
  "source_url": "https://example.com/listing"
}
```

Notes:
- `price`, `bedrooms`, and `bathrooms` must be integers
- `commute_minutes` may be `null` if unavailable
- `features` should be short normalized strings like `parking`, `garden`, `walkable`, `quiet street`
- keep the `source_url`
- `image_urls` are optional for ranking but required for HomesToCompare publishing
- never invent photo URLs; keep only URLs observed in page HTML, page state, JSON-LD, DOM images, network responses, or a fetched API response
- when publishing to HomesToCompare, carry photo verification diagnostics under `external_refs.photo_extraction`
- prefer factual data from the listing page over guessed values
- if you have extraction or commute-estimation diagnostics, keep them under `external_refs`

## Workflow

### Step 1 — Capture the buyer brief

Extract the buyer brief from the user message.
If it is incomplete, ask for:
- target area or commute destination
- budget
- bedroom count
- key priorities

### Step 2 — Gather candidate listings externally

Use available browser/search/API tools to find relevant listings.

Aim for:
- 5 to 12 candidate listings
- multiple sources when possible
- properties plausibly matching budget, location, and bedroom requirements

Prefer public listing pages or structured API responses. Do not pretend to have visited pages you have not actually inspected.

### Step 3 — Normalize listings into JSON

Write the normalized candidate list to a temporary JSON file in the repo, for example:

```bash
mkdir -p .tmp
```

Save a JSON array such as:

```json
[
  {
    "id": "rightmove-123",
    "title": "Station Quarter Flat",
    "price": 235000,
    "bedrooms": 2,
    "bathrooms": 1,
    "location": "Birmingham",
    "commute_minutes": 15,
    "features": ["parking"],
    "description": "Modern flat near New Street.",
    "source_url": "https://www.rightmove.co.uk/..."
  }
]
```

### Step 4 — Run the harness pipeline

Run:

```bash
uv run --extra dev python .pi/skills/browser-house-hunt/run_house_hunt.py \
  --brief "BRIEF_GOES_HERE" \
  --listings-file .tmp/listings.json
```

Optional exports:

```bash
uv run --extra dev python .pi/skills/browser-house-hunt/run_house_hunt.py \
  --brief "BRIEF_GOES_HERE" \
  --listings-file .tmp/listings.json \
  --export-html .tmp/house-hunt-report.html \
  --export-csv .tmp/house-hunt-report.csv
```

HomesToCompare publishing:

```bash
uv run --extra dev python .pi/skills/browser-house-hunt/run_house_hunt.py \
  --brief "BRIEF_GOES_HERE" \
  --listings-file .tmp/listings.json \
  --publish-h2c
```

Only use `--publish-h2c` when the selected listings include verified photos. The harness
will refuse to publish an H2C comparison if selected listings have no verified images.

### Step 5 — Report back to the user

Summarize:
- parsed buyer profile
- ranked listings with score, price, location, key matches, misses, and warnings
- comparison summary
- affordability estimate for the top match
- tour questions
- offer-prep brief
- trace path and export paths if generated
- HomesToCompare overview/photos URL when publishing succeeded, or the validation errors when it did not

## Guardrails

- Do not present outputs as legal, mortgage, survey, inspection, or negotiation advice
- Make clear when values are missing or estimated
- Keep source URLs for every listing
- If commute time was not explicitly retrieved, leave it null rather than inventing it unless the extension's heuristic commute enrichment is being used and clearly marked as estimated
- If browser tools are blocked by a site, say so and move on to another source
- Do not report an H2C comparison as complete when photos are missing or unverified

## Troubleshooting

| Problem | What to do |
|---|---|
| No browser tools available | Ask the user to paste listing URLs or listing details and then run the harness on those |
| Sparse listing data | Normalize what you have, keep missing fields honest, and proceed |
| Script says file is invalid | Ensure the file contains a JSON array of listing objects |
| No good matches after ranking | Tell the user why and suggest relaxing budget, location, or must-haves |

## Files used by this skill

- `./run_house_hunt.py` — helper script that runs the harness on normalized listing JSON
