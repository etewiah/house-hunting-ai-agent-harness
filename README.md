# House Hunting Agent Harness

Open-source reference harness for buyer-side real estate assistants: modular skills, transparent tools, policy guardrails, and evals for real-world house-hunting workflows.

This is not a magical autonomous house buyer. It is a forkable framework for building credible buyer workflows with explicit skills, transparent sources, human approval boundaries, and repeatable tests.

## What It Does

- Captures buyer preferences into structured profiles.
- Ranks mock listings against a buyer brief.
- Explains why listings match or miss.
- Compares shortlists side by side.
- Estimates monthly housing cost.
- Generates tour questions and offer-prep briefs.
- Provides guardrails for legal, financial, inspection, and fair-housing-sensitive boundaries.
- Ships with eval fixtures so changes can be measured.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
house-hunt demo
pytest
```

## Design

The harness has three layers:

- `skills/`: small testable capabilities such as intake, ranking, comparison, affordability, tour prep, and offer brief generation.
- `harness/`: orchestration, state, policies, tracing, approvals, and tool routing.
- `connectors/`: local CSV/JSONL providers, mock APIs, and optional MCP integration points.

## Trust Model

Every factual output should be labeled as one of:

- `listing_provided`
- `user_provided`
- `estimated`
- `inferred`
- `missing`

The harness should never present itself as a lawyer, mortgage advisor, surveyor, inspector, or fiduciary buyer's agent.

## v0.1 Scope

Included:

- CLI demo
- Mock listing dataset
- Buyer preference intake
- Listing ranking and explanations
- Home comparison
- Affordability estimate
- Tour and offer-prep outputs
- Basic eval suite
- MCP connector stub

Not included:

- autonomous browsing
- outbound calling
- negotiation automation
- legal or mortgage advice
- transaction management

