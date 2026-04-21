# Harness Controls

This project uses the harness as a trust boundary around house-hunting agent output. The
controls below make that boundary explicit.

## Control Types

| Control | Direction | Execution | Regulates | Runs |
|---|---|---|---|---|
| `docs/guardrails.md` | Feedforward guide | Inferential | Behaviour | Before implementation and agent use |
| `docs/architecture.md` | Feedforward guide | Inferential | Architecture fitness | Before implementation |
| `src/models/schemas.py` source labels | Feedforward guide | Computational | Behaviour | Runtime |
| `src/harness/policies.py` guardrail checks | Feedback sensor | Computational | Behaviour | Runtime and evals |
| `evals/tests/test_guardrails.py` | Feedback sensor | Computational | Behaviour | Local and CI |
| `evals/tests/test_architecture_boundaries.py` | Feedback sensor | Computational | Architecture fitness | Local and CI |
| `evals/tests/test_ranking.py` | Feedback sensor | Computational | Behaviour | Local and CI |
| `evals/tests/test_explanations.py` | Feedback sensor | Computational | Behaviour | Local and CI |
| `src/harness/tracing.py` | Feedback sensor | Computational | Behaviour and operability | Runtime |

## Behaviour Harness

The behaviour harness checks that generated buyer-facing outputs stay useful and bounded:

- explanations cite source labels instead of presenting unsupported claims
- affordability outputs include assumptions and stay out of mortgage advice
- offer-prep output includes an advice boundary
- sensitive area recommendation language is flagged
- missing data is surfaced instead of silently inferred

## Architecture Fitness Harness

The architecture boundary test keeps the intended layers intact:

- models do not depend on connectors, skills, tools, harness, or UI
- skills do not depend on connectors or UI
- connectors do not depend on UI
- tools do not depend on UI

These checks are intentionally small and deterministic. Add inferential review only where the
behaviour cannot be expressed as a stable rule.

## When To Add A Control

Add or update a guide when an agent repeatedly makes the same bad assumption before writing code.
Add or update a sensor when a mistake can be detected after output is produced.

Prefer computational sensors first: tests, source-label checks, schema validation, boundary checks,
and architecture rules. Use LLM review only for semantic judgment that deterministic checks cannot
cover reliably.
