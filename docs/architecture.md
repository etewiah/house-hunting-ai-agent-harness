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
- mock listing APIs
- optional MCP tools
- maps, schools, calendars, and notification services

## Runtime Flow

1. Capture buyer preferences.
2. Load candidate listings.
3. Rank listings with transparent scoring.
4. Explain matches and missing information.
5. Compare selected homes.
6. Generate tour or offer-prep outputs.
7. Trace every step.

## Agent Access

Coding agents can use the harness directly by reading the repository, importing Python
modules, running the CLI, and executing tests. The MCP server is an optional compatibility
layer for clients that need MCP tool discovery; it is not required for repo-native agent
workflows.
