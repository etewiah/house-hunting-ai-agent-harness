# Architecture

The harness is intentionally modular.

## Layers

### Skills

Skills are small deterministic or model-backed capabilities. Each skill accepts typed inputs and returns typed outputs with source labels.

Initial skills:

- `intake`
- `ranking`
- `explanation`
- `comparison`
- `affordability`
- `market_watch`
- `tour_prep`
- `offer_brief`

### Harness

The harness owns orchestration:

- session state
- memory
- policy checks
- approval gates
- retries
- tracing
- eval hooks

### Connectors

Connectors hide external systems:

- local files
- provider listing APIs
- optional MCP tools
- maps, schools, calendars, and notification services

## Runtime Flow

1. Capture buyer preferences.
2. Load candidate listings.
   - from a configured provider, or
   - from browser/agent-supplied listing data
3. Rank listings with transparent scoring.
4. Explain matches and missing information.
5. Compare selected homes.
6. Generate tour or offer-prep outputs.
7. Trace every step.

In browser-first workflows, an external agent or the project-local Pi extension may also:
- search for listing URLs
- extract listing pages into normalized listing data
- attach extraction diagnostics and quality metadata
- heuristically enrich commute data before ranking

## Agent Access

Coding agents can use the harness directly by reading the repository, importing Python
modules, and executing tests. The MCP server is an optional compatibility
layer for clients that need MCP tool discovery; it is not required for repo-native agent
workflows.
