# Browser-Assisted Change Log

This is a chronological, user-facing log of the major browser-first and Pi-related improvements added to this project.

For a task-oriented usage guide, see:
- [docs/browser-assisted-guide.md](browser-assisted-guide.md)

## Summary

The biggest overall change is this:

- the project no longer assumes a configured listing provider is mandatory
- browser-found, agent-supplied, and user-supplied listings are now first-class
- Pi can now search, extract, normalize, and run the harness through a project-local extension and skill

---

## Phase 1 — Provider-less browser-first harness support

### Added
- optional listing provider in `src/app.py`
- browser-first triage entrypoints in `src/harness/orchestrator.py`
  - `triage_listings(...)`
  - `triage_listing_dicts(...)`
- shared listing normalization in `src/skills/listing_input.py`
- CLI/browser-mode guidance in `src/ui/cli.py`
- browser-mode MCP normalization reuse in `src/ui/mcp_server.py`

### Why it matters
Previously, missing provider configuration could stop the workflow early.
Now, the harness can be used with listings gathered externally.

### How you use it
Use a coding agent or your own scripts to gather listings, then run:

```bash
uv run --extra dev python .pi/skills/browser-house-hunt/run_house_hunt.py \
  --brief "..." \
  --listings-file .tmp/listings.json
```

---

## Phase 2 — Better buyer-brief parsing for realistic property search

### Added
- improved phrase parsing in `src/skills/intake.py`
- more accurate feature detection
- better handling of preferred vs required constraints
- safer token-aware matching

### Why it matters
The harness can now interpret natural-language buyer briefs more reliably.

### How you use it
Give the brief in normal English, for example:

```text
2-bed flat near Birmingham New Street, under £250k, parking preferred
```

---

## Phase 3 — Pi skill for browser-assisted house hunting

### Added
- `.pi/skills/browser-house-hunt/SKILL.md`
- `.pi/skills/browser-house-hunt/run_house_hunt.py`

### Why it matters
Pi and other compatible agent flows now have a documented browser-first skill path.

### How you use it
In Pi:

```text
/skill:browser-house-hunt
```

---

## Phase 4 — Pi extension for search, extraction, and one-shot runs

### Added
Project-local extension under:
- `.pi/extensions/house-hunt-browser/`

### Tools added
- `property_web_search`
- `property_listing_extract`
- `extract_property_listings`
- `run_house_hunt_harness`
- `house_hunt_from_web`

### Command added
- `/house-hunt-smoke`

### Why it matters
Pi can now do the full browser-assisted workflow from inside the repo.

### How you use it
Start Pi in this repo and run:

```text
/reload
/skill:browser-house-hunt
```

Then either:
- use `house_hunt_from_web`, or
- use search -> extract -> harness in separate steps

---

## Phase 5 — Stronger extraction and diagnostics

### Added
- shared extraction core in `.pi/extensions/house-hunt-browser/extractor-core.mjs`
- extraction diagnostics including:
  - parser
  - field sources
  - host
  - hadJsonLd
  - missingFields
  - warnings
  - qualityScore
- trace writing under `.tmp/`

### Why it matters
Extraction is now more transparent and debuggable.

### How you use it
Use:
- `property_listing_extract`
- `extract_property_listings`
- `house_hunt_from_web`

Then inspect the returned diagnostics and `.tmp/` traces.

---

## Phase 6 — Fixture-based extraction tests and validation

### Added
- fixture-based Node tests
- manifest-driven assertions
- fixture validation tooling
- fixture capture workflow
- multiple synthetic fixtures for Rightmove, Zoopla, OnTheMarket, and generic fallback cases

### Why it matters
Portal extraction changes are now more testable and less fragile.

### How you use it
Run:

```bash
cd .pi/extensions/house-hunt-browser
npm test
npm run validate-fixtures
```

Capture a fixture with:

```bash
npm run capture-fixture -- https://example.com/listing
```

---

## Phase 7 — Quality-aware ranking input

### Added
- low-quality filtering before ranking in `house_hunt_from_web`
- `minQualityScore` support with a default of `45`
- clearer failure behavior when no extracted listing passes the threshold

### Why it matters
The one-shot web flow is less likely to rank low-confidence garbage.

### How you use it
Use `house_hunt_from_web` and optionally set `minQualityScore`.

---

## Phase 8 — Heuristic commute enrichment

### Added
- `.pi/extensions/house-hunt-browser/commute-core.mjs`
- commute destination inference from the brief
- commute estimation metadata under `external_refs`
- commute mode support

### Why it matters
Listings with missing commute values can still be ranked more usefully.

### Important caveat
This is heuristic, not a real live maps integration.

### How you use it
Use `house_hunt_from_web` with:
- an inferred commute destination from the brief, or
- an explicit commute destination

---

## Phase 9 — Honest provenance in outputs

### Added
Estimated commute and extraction metadata now appear across:
- ranking warnings
- comparison output
- browser-house-hunt runner output
- CSV export
- HTML export
- explanation text

### Why it matters
The project is more honest about what is:
- listing-provided
- scraped
- estimated
- missing

### How you use it
Open the generated exports or inspect MCP / Pi output details.

---

## Phase 10 — Hardened normalization for messy browser data

### Added
More tolerant normalization on both:
- Python side
- Pi extension side

Examples now handled better:
- `"£250,000"`
- `"3 bedrooms"`
- `"1 bathroom"`
- `"22 min"`
- single-string features
- single-string image URLs

### Why it matters
Real browser-extracted data is often messy. The system is now more forgiving.

### How you use it
Pass listings in with common browser-style field shapes; the harness is now more likely to accept them directly.

---

## Phase 11 — MCP improvements

### Added
Improved MCP tools in `src/ui/mcp_server.py`, including:
- better browser-style input handling
- `max_listings` support for exports
- new high-level `run_house_hunt(...)` tool

### Why it matters
MCP clients now have a one-call browser-first workflow instead of manually orchestrating everything.

### How you use it
Start MCP:

```bash
uv run house-hunt serve
```

Then call:
- `run_house_hunt(...)` for the high-level path, or
- `parse_brief` / `rank_listings` / export tools for lower-level control

---

## Documentation added

### Added
- `docs/browser-assisted-guide.md` — task-oriented usage guide
- `docs/browser-assisted-changelog.md` — chronological change log

### Why it matters
You now have:
- one document for “how do I use this?”
- one document for “what changed over time?”

---

## Current recommended usage

### Best path for Pi users

```text
pi
/reload
/skill:browser-house-hunt
```

Then:
- try `house_hunt_from_web`
- if needed, fall back to:
  - `property_web_search`
  - `extract_property_listings`
  - `run_house_hunt_harness`

### Best path for coding-agent users
- gather listings externally
- save normalized JSON
- run `.pi/skills/browser-house-hunt/run_house_hunt.py`

### Best path for MCP users
- start `uv run house-hunt serve`
- call `run_house_hunt(...)`

---

## Still incomplete or heuristic

The main remaining caveats are:
- commute enrichment is heuristic only
- extraction still depends on heuristic site parsing
- real captured fixtures would improve confidence further
- live Pi smoke verification still needs broader real-world testing
