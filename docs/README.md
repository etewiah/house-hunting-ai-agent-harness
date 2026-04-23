# Documentation Map

This folder contains both stable project docs and the newer browser-first / Pi workflow docs.

## Start here

If you are trying to understand the project quickly, read these first:

1. `../README.md`
   - main project overview
   - highlights CLI, Pi, MCP, and coding-agent usage
2. `browser-assisted-guide.md`
   - practical "how do I use this now?" guide for browser-first workflows
3. `browser-assisted-changelog.md`
   - chronological record of the browser-first and Pi-related improvements

## Core project docs

- `architecture.md`
  - architectural layering and runtime flow
- `guardrails.md`
  - output boundaries, source transparency, and approval gates
- `harness-controls.md`
  - what controls and tests enforce the trust boundary
- `evals.md`
  - what behavior the eval suite is meant to cover
- `roadmap.md`
  - current implementation status, near-term priorities, and later ideas

## Integration and provider docs

- `connectors.md`
  - connector concepts and integration expectations
- `providers.md`
  - provider-facing design notes
- `INTEGRATION_UPDATES.md`
  - HomesToCompare-oriented integration notes, implemented status notes, and remaining coordination items

## Browser-first / Pi docs

- `browser-assisted-guide.md`
  - browser-assisted usage across Pi, coding agents, and MCP
- `browser-assisted-changelog.md`
  - timeline of browser-first improvements
- `../.pi/extensions/house-hunt-browser/README.md`
  - Pi extension tools, smoke test, fixture capture, and extension testing
- `../.pi/skills/browser-house-hunt/SKILL.md`
  - Pi skill instructions for browser-assisted house hunting

## Which doc should I read?

### I want to use Pi with this repo
- `../README.md`
- `browser-assisted-guide.md`
- `../.pi/extensions/house-hunt-browser/README.md`

### I want to know what changed recently
- `browser-assisted-changelog.md`

### I want to understand trust/guardrails
- `guardrails.md`
- `harness-controls.md`

### I want to integrate another client or provider
- `connectors.md`
- `providers.md`
- `INTEGRATION_UPDATES.md`

### I want to understand the architecture
- `architecture.md`
- `roadmap.md`
