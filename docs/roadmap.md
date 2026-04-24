# Roadmap

This roadmap reflects the current state of the project more accurately than the original
v0.1 sketch. For browser-first usage details, see:
- `docs/browser-assisted-guide.md`
- `docs/browser-assisted-changelog.md`

## Implemented now

### Core harness
- MCP and trace command utilities
- Optional provider-backed listing search
- Browser-supplied / user-supplied listing support
- Preference intake
- Listing ranking with machine-readable score breakdowns
- Structured comparison result with recommendation, trade-offs, confidence, and verification items
- Affordability estimate
- Tour prep and offer brief
- CSV and HTML export
- Source-aware verification checklist for missing or risky buyer decision fields
- Eval suite
- Optional MCP server

### Browser-first / Pi workflow
- project-local Pi skill
- project-local Pi extension
- web search for listing URLs
- listing extraction and normalization
- extraction diagnostics and quality scoring
- quality filtering before ranking
- heuristic commute enrichment
- browser-first Python runner script
- browser-first MCP workflow tool

## Near-term priorities

- real captured fixtures for portal extraction, not just synthetic fixtures
- more portal-specific extraction hardening, especially fallback-heavy cases
- clearer trace inspection / trace viewer tooling
- richer export surfacing for extraction provenance and confidence
- more browser-assisted smoke testing against live pages
- buyer-specific decision weights and richer provider-backed data for tenure,
  service charges, EPC, council tax, condition, chain status, outdoor space,
  flood risk, and broadband

## Later

- non-heuristic commute or travel-time provider integration
- provider-specific listing connectors beyond the current set
- market watch / saved-search scheduling
- calendar integrations
- notification adapters
- human handoff workflows
