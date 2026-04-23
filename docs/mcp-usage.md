# MCP Usage Guide

This guide explains how to use the optional MCP server exposed by this project.

For a broader browser-first overview, see:
- `browser-assisted-guide.md`
- `browser-assisted-changelog.md`

## What the MCP server is for

The MCP server is an optional compatibility layer for clients that want MCP tool discovery
and tool calls.

It is useful when:
- your client already speaks MCP
- you want structured tool calls instead of importing Python modules directly
- you want a high-level house-hunt workflow available through one MCP tool

It is not required when:
- you are using Pi inside this repo
- you are using a coding agent that can access the repository directly
- you are happy to call Python code or scripts without MCP

## Start the MCP server

```bash
uv run house-hunt serve
```

If your MCP client needs static configuration, use something like:

```json
{
  "mcpServers": {
    "house-hunt": {
      "command": "uv",
      "args": ["run", "house-hunt", "serve"],
      "cwd": "/path/to/house-hunting-ai-agent-harness"
    }
  }
}
```

## MCP tools available

Current tools exposed by `src/ui/mcp_server.py`:

### Harness tools (original 9)

- `parse_brief`
- `rank_listings`
- `run_house_hunt`
- `compare_homes`
- `estimate_affordability`
- `tour_questions`
- `offer_brief`
- `export_csv`
- `export_html`

### Browser-assisted extraction tools (Tier 2, added for Claude Code parity)

- `property_web_search`
- `property_listing_extract`
- `extract_property_listings`
- `house_hunt_from_web`

## Browser-assisted tool reference

### `property_web_search`

Search the web for candidate listing URLs using DuckDuckGo, scoped to major UK
portals.

| Argument | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | Search query or buyer brief |
| `max_results` | integer | 8 | Max results to return (1–20) |
| `sites` | list[string] | null | Domain whitelist; defaults to Rightmove, Zoopla, OnTheMarket |

Returns: `{ results: [{title, url}, ...], count }`

Example:
```python
property_web_search(query="2-bed flat Birmingham under £250k", max_results=6)
```

### `property_listing_extract`

Fetch one property listing page and extract normalized fields using site-specific
parsers (Rightmove, Zoopla, OnTheMarket) with JSON-LD and text fallbacks.

| Argument | Type | Default | Description |
|---|---|---|---|
| `url` | string | required | Property listing URL |
| `commute_minutes` | integer | null | Optional known commute time |

Returns: `{ listing, diagnostics, quality, missing_fields, warnings, parser }`

The `diagnostics` object includes:
- `parser`: which parser was used (`rightmove`, `zoopla`, `onthemarket`, `generic`)
- `qualityScore`: 0–100 extraction quality score
- `fieldSources`: per-field provenance (`site_specific`, `json_ld`, `text_regex`, etc.)
- `missingFields`: list of fields that could not be extracted
- `warnings`: list of human-readable warnings
- `hadJsonLd`: whether a JSON-LD block was found on the page

Example:
```python
property_listing_extract(url="https://www.rightmove.co.uk/properties/123")
```

### `extract_property_listings`

Batch extraction of multiple listing URLs. Each URL is fetched and run through
`property_listing_extract`. Failed URLs are collected separately so you can
proceed with the successful ones.

| Argument | Type | Default | Description |
|---|---|---|---|
| `urls` | list[string] | required | Listing URLs (max 20) |
| `commute_minutes_by_url` | dict[string, int] | null | Optional URL → commute time mapping |

Returns: `{ extracted: [...], failed: [...], extracted_count, failed_count }`

Example:
```python
extract_property_listings(
    urls=["https://www.rightmove.co.uk/...", "https://www.zoopla.co.uk/..."]
)
```

### `house_hunt_from_web`

End-to-end browser-assisted flow: search → extract with quality scoring →
heuristic commute enrichment → quality filter → return accepted listings.
Call `run_house_hunt` afterwards with the `accepted_listings` to rank and
prepare next steps.

| Argument | Type | Default | Description |
|---|---|---|---|
| `brief` | string | required | Buyer brief in plain English |
| `max_results` | integer | 6 | Max search results (1–12) |
| `sites` | list[string] | null | Domain whitelist |
| `min_quality_score` | integer | 45 | Minimum quality score to include (0–100) |
| `commute_destination` | string | null | Destination for heuristic commute enrichment |
| `commute_mode` | string | `"transit"` | `transit`, `driving`, or `walking` |

Returns: `{ search_results, search_count, extracted, extracted_count,
accepted_listings, accepted_count, failed, failed_count, average_quality,
filtered_out_low_quality, commute_destination, commute_mode, min_quality_score }`

Example end-to-end workflow:
```python
# Step 1: search + extract + filter
web = house_hunt_from_web(
    brief="2-bed flat near Birmingham New Street, under £250k, parking preferred",
    max_results=6,
    min_quality_score=45,
    commute_destination="Birmingham",
    commute_mode="transit",
)

# Step 2: rank and prepare next steps
result = run_house_hunt(
    brief="2-bed flat near Birmingham New Street, under £250k, parking preferred",
    listings=web["accepted_listings"],
    limit=5,
)
```

## Best MCP entrypoint

If you want the simplest browser-first workflow, use:

- `run_house_hunt(brief, listings, limit=5)`

This is the highest-level MCP tool and returns a structured result containing:
- `buyer_profile`
- `acquisition_summary`
- `area_context_summary`
- `area_evidence_rollup`
- `triage_warnings`
- `ranked_listings`
- `explanations`
- `comparison`
- `next_steps`

### Area evidence confidence fields

`area_evidence_rollup` includes trust-scanning fields that summarize how complete area evidence is for the ranked set:

- `listing_count_considered`
- `listings_with_area_context`
- `total_evidence_items`
- `total_area_warnings`
- `evidence_by_source`
- `top_categories`
- `coverage_ratio`
- `estimated_ratio`
- `confidence_band`
- `confidence_reason`

Interpret `confidence_band` as:

- `high`: broad listing coverage with multi-item evidence and lower estimated-only share
- `medium`: useful but partial evidence coverage
- `low`: sparse or mostly estimated evidence, or no area evidence

Use this as a routing signal:

- high/medium: continue with comparison and tour prep
- low: gather more area evidence before finalizing a shortlist

Use this when you already have listings from:
- browser tools
- search APIs
- another scraper
- user-supplied input

## Example MCP workflow

### Option A — high-level path

1. collect listings externally
2. call `run_house_hunt(...)`
3. optionally call `export_html(...)` or `export_csv(...)`

### Option B — lower-level path

1. call `parse_brief(...)`
2. call `rank_listings(...)`
3. call `compare_homes(...)`
4. call `estimate_affordability(...)`
5. call `tour_questions(...)`
6. call `offer_brief(...)`
7. call `export_html(...)` or `export_csv(...)`

## Listing input expectations

The MCP server accepts browser-style listing payloads and normalizes them before ranking.

Examples of tolerated inputs include:
- `"£250,000"`
- `"3 bedrooms"`
- `"1 bathroom"`
- `"22 min"`
- `features: "parking"`
- ranked listing dicts with nested `listing` payloads

Expected listing shape conceptually:

```json
{
  "id": "listing-1",
  "title": "Station Quarter Flat",
  "price": 235000,
  "bedrooms": 2,
  "bathrooms": 1,
  "location": "Birmingham",
  "commute_minutes": 15,
  "features": ["parking"],
  "description": "Modern flat near New Street.",
  "source_url": "https://example.com/listing"
}
```

## Exports through MCP

### `export_csv(...)`
Supports:
- ranked listings from `rank_listings(...)`
- `output_path`
- `max_listings`

### `export_html(...)`
Supports:
- ranked listings from `rank_listings(...)`
- `output_path`
- `max_listings`

Exports now preserve more browser-first metadata where present, including:
- extraction quality metadata
- commute estimation metadata

## LLM behavior in MCP mode

The MCP server uses the same provider detection as the CLI.

See:
- `providers.md`

If no model provider is configured:
- intake falls back to regex parsing
- explanation behavior remains deterministic where appropriate

## When to prefer MCP vs direct repo usage

Prefer MCP when:
- your client already has a good MCP integration
- you want tool discovery and structured calls

Prefer direct repo usage when:
- you are using Pi locally in this repo
- you want the project-local Pi extension
- you want to run `.pi/skills/browser-house-hunt/run_house_hunt.py`
- you want to import `src/` modules directly

## Related files

- `src/ui/mcp_server.py`
- `src/skills/listing_input.py`
- `docs/browser-assisted-guide.md`
- `docs/providers.md`
