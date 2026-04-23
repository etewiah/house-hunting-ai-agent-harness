# Connectors

Connectors keep external systems out of core skills and preserve the provider-agnostic
shape of the harness.

## Current connectors

### Listing providers
- `src/connectors/homestocompare_connector.py`
  - HomesToCompare-backed listing search adapter
  - also includes comparison creation support for top-ranked listings
- `src/connectors/local_csv.py`
  - CSV-backed listing source adapter for explicit local datasets

### LLM providers
- `src/connectors/provider_factory.py`
  - auto-detects or selects the configured LLM adapter
- provider adapters under `src/connectors/`
  - used by intake and explanation when an LLM is configured

### What is not a core connector
- `src/ui/mcp_server.py`
  - optional MCP compatibility layer, not the primary internal connector pattern

## Connector contract

A listing connector should expose:

- `search(profile) -> list[Listing]`

Comparison-capable connectors may also expose operations such as:
- `create_comparison(listings)`
- `create_comparison(left_url, right_url)`

## Design expectations

Real providers should:
- keep the core harness provider-agnostic
- preserve source URLs where possible
- avoid leaking provider-specific response shapes into skills
- preserve raw payloads or provenance references when useful for auditability
- degrade gracefully when optional data such as commute is unavailable

## Browser-first note

In browser-assisted workflows, the project can bypass a listing connector entirely:
- an agent or Pi extension can gather listings externally
- `listing_from_dict(...)` normalizes them into `Listing`
- `HouseHuntOrchestrator.triage_listings(...)` or `triage_listing_dicts(...)` ranks them directly

That browser-first path is now a first-class workflow, not just a fallback.
