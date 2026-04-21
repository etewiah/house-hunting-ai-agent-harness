# HomesToCompare Integration Notes

HomesToCompare is a useful platform adapter for this harness, but it is not a core
assumption. The harness should continue to work with local files, user-supplied listing
data, and other platforms.

## Current Connector Surface

The existing connector supports:

- Reading listings through `H2CListingConnector.search(...)`.
- Creating a comparison through `HomesToCompareConnector.create_comparison(...)`.

The current comparison payload is intentionally simple: listings plus a source label.
Future platform-specific enrichments should preserve this simple path.

## Possible Future Platform Capabilities

- Read richer listing or comparison metadata from a machine-readable page or API.
- Write optional enrichments back to H2C, such as commute estimates, area evidence,
  image observations, or comparison narratives.
- Persist a buyer journey as an H2C quest or equivalent saved-search container.
- Return shareable comparison and machine-readable URLs from export flows.

## Adapter Boundaries

H2C-specific logic should stay in connector or exporter modules. Core models should use
generic fields such as `external_refs`, `location_data`, `area_data`, and provider/source
labels rather than H2C-only names.

## Open Questions

- What is the stable API contract for richer comparison payloads?
- Which H2C fields are safe for the harness to write back?
- Should write access use a different credential from read access?
- How long do shareable comparison URLs remain available?
