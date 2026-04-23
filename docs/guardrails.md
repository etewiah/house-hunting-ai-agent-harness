# Guardrails

## Advice Boundaries

The harness must not represent itself as:

- a lawyer
- a mortgage advisor
- a surveyor
- an inspector
- a fiduciary buyer's agent

Outputs should use clear boundaries such as:

> This is a preparation aid, not legal, mortgage, survey, inspection, fiduciary, or negotiation advice.

## Fair Housing Caution

Avoid steering users based on protected or sensitive characteristics. Neighborhood fit should be framed through user-provided preferences and objective property attributes, not protected-class assumptions.

## Source Transparency

Every claim should be labeled:

- `listing_provided`
- `user_provided`
- `estimated`
- `inferred`
- `missing`

This is especially important in browser-assisted flows where some values may be:
- scraped from listing pages
- inferred from page structure
- estimated heuristically, such as commute enrichment

## Approval Gates

Human approval is required before:

- contacting agents
- scheduling tours
- sending offer language
- making financial recommendations
- producing legal interpretations

