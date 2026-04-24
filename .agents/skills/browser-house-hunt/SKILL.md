---
name: browser-house-hunt
description: Find property listings with WebSearch/WebFetch or Codex-in-chrome tools, normalize them into Listing-shaped dicts, and run the house-hunting harness via the `house-hunt` MCP server. Use when a user wants real candidate properties ranked against a buyer brief.
metadata:
  tags: house-hunt, browser, listings, ranking, property
---

# Browser House Hunt (Codex)

Use this skill when the user wants help finding actual properties to buy or rent and you have web or browser tools available in this Codex session.

This skill treats **web discovery** and **harness evaluation** as separate steps:

1. collect candidate listings from the web using WebSearch / WebFetch / Codex-in-chrome
2. normalize each listing into the repo's `Listing` shape
3. run the harness pipeline using those supplied listings via the `house-hunt` MCP server
4. report ranked matches, explanations, comparison, affordability, tour prep, and next steps

If the `house-hunt` MCP server is not available, fall back to the existing `run-house-hunt` skill (which calls `build_app()` directly without discovery).

## Tool preferences

Prefer, in this order:

1. **`run_house_hunt` (MCP)** — one call, returns structured result containing profile, ranked listings, explanations, comparison, affordability, tour questions, and offer brief
2. **`rank_listings` + `compare_homes` + `estimate_affordability` + `offer_brief` (MCP)** — when you need more granular control over the pipeline steps
3. **The existing `run-house-hunt` skill** — fallback when MCP is unavailable or when no web discovery is needed

For web discovery and extraction, prefer in this order:

1. **`house_hunt_from_web` (MCP)** — end-to-end: search → extract with site-specific parsers → enrich commute → filter by quality (Tier 2, recommended)
2. **`property_web_search` + `extract_property_listings` (MCP)** — granular control: discover with DuckDuckGo, extract with quality diagnostics (Tier 2)
3. **`WebSearch` + `WebFetch`** — basic path: search with built-in tools, generic extraction (Tier 1)
4. **`Codex-in-chrome` `navigate` + `read_page`** when a site blocks WebFetch or requires JavaScript
5. **Ask the user for listing URLs or data** if web tools are unavailable or blocked

For batches of 3+ URLs, delegate to the **`listing-extractor` subagent** which processes them in parallel and returns diagnostics.

## Listing schema to normalize into

Each candidate listing should become a JSON object with these fields:

```json
{
  "id": "unique-id-or-url-slug",
  "title": "Property title or address",
  "price": 250000,
  "bedrooms": 2,
  "bathrooms": 1,
  "location": "City or postal area",
  "commute_minutes": 20,
  "features": ["parking", "garden", "quiet street"],
  "description": "Short summary of key aspects",
  "source_url": "https://example.com/listing/123"
}
```

### Field rules

- **`id`** (string): unique identifier or URL slug. Use hostname + path slug, or a sequential ID.
- **`title`** (string): listing title, property address, or heading from the page.
- **`price`** (integer): sale price in whole pounds (no currency symbol, no commas). Must be an integer.
- **`bedrooms`** (integer): count of bedrooms. Must be an integer.
- **`bathrooms`** (integer): count of bathrooms. Must be an integer.
- **`location`** (string): city, area, postal code, or neighborhood. Used for ranking and comparison.
- **`commute_minutes`** (integer or null): commute time to a reference point. Null if unavailable or not estimated. Do not invent this; leave it null if you cannot source it.
- **`features`** (list of strings): normalized short strings like `parking`, `garden`, `garage`, `walkable`, `quiet street`, `balcony`, `lift`. Extract from the listing text; do not invent.
- **`description`** (string): a few sentences summarizing the property, key features, condition, or neighborhood context.
- **`source_url`** (string): the canonical URL of the listing. Always preserve this.

### Optional fields

- **`image_urls`** (optional, list of strings or string): image URL(s) from the listing, if you captured them. Not required; useful for diagnostics.
- **`external_refs`** (optional, object): any metadata you want to carry through (for example, extraction quality, parser used, commute source). The harness will preserve this in downstream outputs.

## Workflow

### Step 1 — Capture the buyer brief

Extract the buyer brief from the user's message. If it is incomplete, ask for:

- target area or commute destination
- budget (e.g. £650k)
- bedroom count (e.g. 3-bed)
- key priorities (e.g. garden, quiet street, schools, parking, walkable)

Example: `"3-bed near Surbiton, budget £650k, max 45 min commute to Waterloo, need a garden"`

### Step 2 — Gather candidate listings externally

Use available web tools to find relevant listings. Aim for:

- 5 to 12 candidate listings
- multiple sources when possible (Rightmove, Zoopla, OnTheMarket, or others)
- properties plausibly matching budget, location, and bedroom requirements

Prefer public listing pages or structured API responses. Do not pretend to have visited pages you have not actually inspected.

Use WebSearch to find candidate URLs, then WebFetch or Codex-in-chrome to fetch the page content.

Example WebSearch queries:

- `2-bed flat to rent Birmingham city centre`
- `3-bedroom house for sale Surbiton London`
- `site:rightmove.co.uk 4-bed Bristol under £500k`

### Step 3 — Normalize listings into JSON

For each page you fetched, extract the fields listed above into a JSON object. Key rules:

- Do not invent missing fields. Leave them null or omit them if you cannot source them from the page.
- Keep the source URL for every listing.
- Convert prices to integers (remove £, commas, decimals if necessary).
- Normalize bedroom/bathroom counts to integers.
- Extract feature keywords from the text; do not guess.
- If commute time is not on the page, leave `commute_minutes` null rather than inventing an estimate.

After normalizing, save the listing JSON array to a temp file:

```bash
mkdir -p .tmp
```

Write a JSON array like:

```json
[
  {
    "id": "rightmove-123456",
    "title": "Modern 2-bed flat, city centre",
    "price": 235000,
    "bedrooms": 2,
    "bathrooms": 1,
    "location": "Birmingham",
    "commute_minutes": null,
    "features": ["parking", "modern"],
    "description": "Recently renovated flat in city centre with allocated parking.",
    "source_url": "https://www.rightmove.co.uk/properties/..."
  }
]
```

### Step 4 — Run the harness pipeline

Once you have normalized listings, call the `run_house_hunt` MCP tool:

```
run_house_hunt(brief="3-bed near Surbiton, budget £650k", listings=[...], limit=5)
```

The tool will return a structured result containing:

- `buyer_profile` — parsed preferences
- `ranked_listings` — sorted by score, with matched/missed features and warnings
- `explanations` — why each top listing ranked as it did
- `comparison` — side-by-side summary of the top 3
- `next_steps` — affordability estimate, tour questions, offer brief, guardrails notice

### Step 5 — Report back to the user

Summarize clearly:

- **Parsed buyer profile** — confirm the brief was understood correctly (location, budget, beds, commute, priorities)
- **Ranked listing table** — title, score out of 100, price, bedrooms, location, key matches, key misses, and any warnings
- **Comparison summary** — top 3 head-to-head
- **Affordability estimate** for the top match (deposit, loan, monthly payment, assumptions)
- **Tour questions** — what to ask on a viewing of the top match
- **Offer brief** — points to consider when making an offer on the top match
- **Boundary notice** — the harness's disclaimer about advice limits
- **Trace path** — path to any exported files or trace data

## Guardrails

- Do not present outputs as legal, mortgage, survey, inspection, fiduciary, or negotiation advice.
- Always mark factual claims by source (e.g. "listing says 3 beds", "estimated based on brief").
- Call out missing information explicitly (e.g. "commute time not listed; assumed null").
- Keep source URLs for every listing so the user can verify.
- If you could not extract commute time from a page, leave it null rather than inventing it (unless you used a heuristic commute estimator, which should be marked as estimated).
- If a site blocks your access, say so and move to another source.

## Troubleshooting

| Problem | What to do |
|---------|-----------|
| No web tools available | Ask the user to paste listing URLs or listing details. Then run the harness on those supplied listings. |
| Sparse listing data | Normalize what you have, mark missing fields explicitly, and proceed. The harness will warn about missing features. |
| Site blocks WebFetch or WebSearch | Try `Codex-in-chrome` `navigate` + `read_page` if available, or ask the user to paste the listing. |
| `house-hunt` MCP server not loaded | Verify `.mcp.json` exists and `uv run house-hunt serve` works from the repo root. Fall back to the `run-house-hunt` skill. |
| Script says file is invalid | Ensure the listings file contains a valid JSON array of listing objects (not a single object). |
| No good matches after ranking | The brief may be too restrictive (budget too low, location too specific, too many must-haves). Ask the user if they want to relax constraints. |

## Key files used by this skill

- `src/app.py` — wires config, LLM, listings, orchestrator (consulted by MCP server)
- `src/harness/orchestrator.py` — the full pipeline: intake → triage → explain → compare → next steps
- `src/ui/mcp_server.py` — the MCP server exposing the harness tools
- `.pi/skills/browser-house-hunt/run_house_hunt.py` — standalone Python script for batch runs (referenced by MCP `run_house_hunt_harness`)
- `docs/mcp-usage.md` — detailed MCP tool documentation
- `docs/browser-assisted-guide.md` — broader context on browser-first workflows
