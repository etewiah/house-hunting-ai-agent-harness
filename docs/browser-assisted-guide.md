# Browser-Assisted House Hunt Guide

This document tracks the main browser-first and agent-first capabilities that have been added to the project, what problem each solves, and how you can actually use them.

## Who this is for

Use this guide if you want to:
- run the house-hunt workflow without a configured listing provider
- use Pi or another coding agent to find listings on the web first
- pass user-supplied or browser-extracted listings into the Python harness
- understand what is implemented already vs what is still heuristic

## Current status at a glance

The project now supports three main usage modes:

1. **Standalone CLI with provider**
   - Uses HomesToCompare or CSV-backed listings
   - Command: `uv run house-hunt`

2. **Browser-assisted / coding-agent workflow without provider**
   - An agent finds listings externally, normalizes them, then runs the harness
   - Main Python helper: `.pi/skills/browser-house-hunt/run_house_hunt.py`

3. **Pi extension + skill workflow**
   - Pi can search, extract, normalize, filter, enrich, and run the harness
   - Main extension: `.pi/extensions/house-hunt-browser/`
   - Main skill: `.pi/skills/browser-house-hunt/SKILL.md`

## What changed

### 1. Listing provider is now optional

Previously the app could hard-fail if no listing provider was configured.

Now:
- `build_app()` allows no provider
- `HouseHuntOrchestrator` supports browser-supplied listings
- provider-backed search is optional rather than mandatory

Use when:
- you want Pi, Codex, or another agent to browse first
- you want to paste your own listing data into the harness

## New browser-first harness entrypoints

### Python orchestrator methods

Available on `HouseHuntOrchestrator`:
- `triage_listings(candidates)`
- `triage_listing_dicts(candidates)`

These let you rank supplied listings directly without needing a provider.

### Python runner script

Use:

```bash
uv run --extra dev python .pi/skills/browser-house-hunt/run_house_hunt.py \
  --brief "2-bed flat near Birmingham New Street, under £250k, parking preferred" \
  --listings-file .tmp/listings.json
```

Optional exports:

```bash
uv run --extra dev python .pi/skills/browser-house-hunt/run_house_hunt.py \
  --brief "2-bed flat near Birmingham New Street, under £250k, parking preferred" \
  --listings-file .tmp/listings.json \
  --export-html .tmp/report.html \
  --export-csv .tmp/report.csv
```

## Pi extension capabilities

Extension location:
- `.pi/extensions/house-hunt-browser/`

### Tools

- `property_web_search`
  - searches the web for candidate listing URLs
- `property_listing_extract`
  - extracts one listing page into normalized listing data
- `extract_property_listings`
  - extracts multiple listing pages
- `run_house_hunt_harness`
  - runs the Python harness on normalized listings
- `house_hunt_from_web`
  - end-to-end search + extract + filter + enrich + rank flow

### Command

- `/house-hunt-smoke <brief>`
  - smoke-tests the browser-assisted flow inside Pi

### Typical Pi workflow

```text
pi
/reload
/skill:browser-house-hunt
```

Then either:
- use `house_hunt_from_web` for the one-shot flow, or
- use `property_web_search` -> `extract_property_listings` -> `run_house_hunt_harness`

## Extraction quality and diagnostics

Browser extraction now carries diagnostics so the project can be more honest about scraped data.

Each extracted listing can include metadata such as:
- parser used
- field-level provenance
- quality score
- missing fields
- warnings
- host
- whether JSON-LD was found

This metadata is stored in `external_refs` and carried into downstream ranking/export paths where possible.

## Quality filtering before ranking

The end-to-end web flow now supports minimum extraction quality filtering.

In `house_hunt_from_web`:
- `minQualityScore` defaults to `45`
- listings below that threshold are filtered out before ranking
- if nothing passes, the tool fails clearly instead of ranking junk

Use this when:
- extraction is noisy
- you want fewer but cleaner candidates

## Heuristic commute enrichment

The Pi extension can now estimate missing commute times before ranking.

It supports:
- inferring a commute destination from the brief
- explicit commute destination input
- basic commute mode (`transit`, `driving`, `walking`)
- storing commute estimation metadata under `external_refs`

Important:
- this is **heuristic**, not a real maps API integration
- estimated commute values are marked as estimated in downstream outputs

## Trust and provenance improvements

Estimated commute values are now surfaced as estimated across:
- ranking warnings
- comparison output
- CLI/browser-house-hunt runner output
- HTML export
- CSV export
- explanation text

This helps distinguish:
- listing-provided values
- extracted values
- heuristic estimates

## Input normalization hardening

The project now tolerates messier browser-supplied payloads.

### Python-side normalization

`src/skills/listing_input.py` now handles values like:
- `"£250,000"`
- `"3 bedrooms"`
- `"1 bathroom"`
- `"22 min"`
- `features: "parking"`
- `image_urls: "https://...jpg"`

### Extension-side normalization

The Pi extension now also tolerates browser-style input before running the harness.

This means agents no longer need to perfectly sanitize every field first.

## Export improvements

### CSV export now includes
- extraction quality score
- extraction parser
- commute estimated flag
- commute destination
- commute mode

### HTML export now includes
- extraction metadata
- commute estimation metadata
- the shared boundary/advice notice
- correct `max_listings` enforcement

## MCP server improvements

MCP server location:
- `src/ui/mcp_server.py`

### Available MCP tools now include
- `parse_brief`
- `rank_listings`
- `run_house_hunt`
- `compare_homes`
- `estimate_affordability`
- `tour_questions`
- `offer_brief`
- `export_csv`
- `export_html`

### New high-level MCP tool

`run_house_hunt(brief, listings, limit=5)` now returns:
- buyer profile
- triage warnings
- ranked listings
- explanations
- comparison
- next steps

This is the MCP equivalent of the browser-first orchestrated workflow.

## Testing and reliability work added

### Python tests
The Python suite now covers:
- browser-mode orchestrator behavior
- intake improvements
- ranking warnings for estimated commute
- comparison output for estimated commute
- export metadata rendering
- listing input normalization
- MCP server browser-first workflows

### Extension tests
The extension now has tests for:
- extraction fixtures
- fixture validation
- commute enrichment
- listing normalization

### Useful commands

Python:

```bash
uv run --extra dev pytest
```

Extension:

```bash
cd .pi/extensions/house-hunt-browser
npm test
npm run validate-fixtures
```

## What is still heuristic or incomplete

These parts still need caution:

1. **Commute enrichment**
   - heuristic only
   - not backed by a live maps provider

2. **Portal extraction**
   - improved, but still heuristic
   - best covered for Rightmove / Zoopla / OnTheMarket

3. **Fixtures**
   - current fixture suite is strong but largely synthetic
   - real captured fixtures would improve confidence further

4. **Live Pi smoke verification**
   - implemented, but not fully verified against live sites from every environment

## Recommended ways to use it today

### If you use Pi

Best path:
1. start `pi` in this repo
2. run `/reload`
3. use `/skill:browser-house-hunt`
4. try `house_hunt_from_web`
5. if results are weak, fall back to:
   - `property_web_search`
   - `extract_property_listings`
   - `run_house_hunt_harness`

### If you use Codex / Claude Code / another coding agent

Best path:
1. gather listings externally
2. normalize them into `Listing`-shaped dicts
3. run:

```bash
uv run --extra dev python .pi/skills/browser-house-hunt/run_house_hunt.py \
  --brief "..." \
  --listings-file .tmp/listings.json
```

### If you use MCP

Best path:
1. start the server:

```bash
uv run house-hunt serve
```

2. call either:
- `run_house_hunt(...)` for the high-level workflow, or
- `parse_brief` + `rank_listings` + export tools for more control

## Main files to know about

Core browser-first Python flow:
- `src/app.py`
- `src/harness/orchestrator.py`
- `src/skills/listing_input.py`
- `.pi/skills/browser-house-hunt/run_house_hunt.py`

Pi extension:
- `.pi/extensions/house-hunt-browser/index.ts`
- `.pi/extensions/house-hunt-browser/extractor-core.mjs`
- `.pi/extensions/house-hunt-browser/commute-core.mjs`
- `.pi/extensions/house-hunt-browser/normalization-core.mjs`

Pi skill:
- `.pi/skills/browser-house-hunt/SKILL.md`

Exports:
- `src/skills/export/csv_exporter.py`
- `src/skills/export/html_exporter.py`

MCP:
- `src/ui/mcp_server.py`

## Bottom line

If you want a simple answer:

- **Yes, the project now supports browser-first use without a provider.**
- **Yes, Pi can search/extract/rank listings through the project-local extension.**
- **Yes, extracted and estimated data is now surfaced more honestly in outputs.**
- **Yes, there is still more to do, especially around live portal verification and non-heuristic commute data.**
