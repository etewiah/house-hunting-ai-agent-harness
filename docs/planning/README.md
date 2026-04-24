# Planning Notes

These documents describe the harness as a portable set of capabilities, not as a
single-country or single-platform product plan.

## Principles

- Keep the core harness provider-agnostic.
- Put external services behind adapters.
- Let the LLM choose relevant capabilities from the buyer brief.
- Require provenance, freshness, and uncertainty labels for enriched data.
- Degrade gracefully when a provider, platform, or geography is unsupported.
- Keep platform-specific behavior in integration notes, not core planning docs.

## Capability Specs

- [01 - Commute and Travel Time Enrichment](01-commute-times.md)
- [02 - Richer AI-Powered Comparison](02-richer-comparison.md)
- [03 - Area Intelligence Enrichment](03-area-data.md)
- [04 - Persistent Sessions](04-persistent-sessions.md)
- [05 - Listing Image Analysis](05-image-analysis.md)
- [06 - Session Export](06-export.md)
- [07 - Verified H2C Comparison Publishing](07-h2c-verified-comparison-publishing.md)

## Integration Notes

Provider and platform-specific plans should live under `docs/integrations/`. Those
documents can mention concrete endpoints, credentials, API limits, and regional data
sources without constraining the harness contract.
