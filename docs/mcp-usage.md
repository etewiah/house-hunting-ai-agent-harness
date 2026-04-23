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

- `parse_brief`
- `rank_listings`
- `run_house_hunt`
- `compare_homes`
- `estimate_affordability`
- `tour_questions`
- `offer_brief`
- `export_csv`
- `export_html`

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
