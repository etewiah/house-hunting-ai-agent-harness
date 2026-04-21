# Agent Guide

Use this repository directly. You do not need to start an MCP server unless the user
explicitly wants MCP tool calls from another client.

## Default Workflow

1. Read the buyer brief or task.
2. Use repo-native modules in `src/skills/` and `src/harness/`.
3. Normalize listing data into `src.models.schemas.Listing`.
4. Use `HouseHuntOrchestrator` or the individual skills to rank, compare, explain, and
   export results.
5. Run `uv run --extra dev pytest` after code changes.

## Useful Commands

```bash
uv run house-hunt demo
uv run house-hunt demo --export-path /tmp/house-hunt-report.html
uv run house-hunt demo --export-path /tmp/house-hunt-shortlist.csv
uv run --extra dev pytest
```

## Codex Skills

This repo includes a project-local Codex skill at
`.codex/skills/run-house-hunt/SKILL.md`. Use it when the user asks Codex to run the
house-hunting pipeline from a buyer brief.

Example prompt:

```text
Use the run-house-hunt skill for: 3-bed near Bristol, budget £400k, need parking and a garden
```

## Important Modules

- `src/models/schemas.py`: shared dataclasses and source labels.
- `src/models/capabilities.py`: provider-facing protocols.
- `src/harness/orchestrator.py`: high-level workflow.
- `src/skills/ranking.py`: scoring and matching.
- `src/skills/comparison.py`: non-LLM comparison fallback.
- `src/skills/export/`: CSV and HTML export.
- `docs/planning/`: provider-agnostic capability specs.
- `docs/integrations/`: provider or platform-specific notes.

## Design Rules

- Keep the core harness provider-agnostic.
- Add concrete services behind adapters, not inside core skills.
- Preserve source labels: `listing_provided`, `user_provided`, `estimated`, `inferred`,
  or `missing`.
- Prefer graceful warnings over hard failures when data is unavailable.
- Do not present outputs as legal, mortgage, survey, inspection, or valuation advice.

## MCP

`uv run house-hunt serve` exposes MCP tools for compatible clients. Treat this as an
optional interface, not the primary way to use the harness from a coding agent.
