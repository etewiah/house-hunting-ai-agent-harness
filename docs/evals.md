# Evals

The repo should measure behavior from day one.

## Initial Evals

- Ranking quality
- Explanation fidelity
- Missing-data handling
- Guardrail compliance
- Cost-estimate sanity

## Dataset Files

- `evals/datasets/buyer_profiles.jsonl`
- `evals/datasets/listings_small.jsonl`
- `evals/datasets/comparison_cases.jsonl`

## Useful Metrics

- Top-k match accuracy against expected fixtures
- Explanation references only known data
- No prohibited advice claims
- Missing fields are called out instead of hallucinated
- Harness control coverage by behaviour and architecture category
- Guardrail violations and warnings by generated output type
