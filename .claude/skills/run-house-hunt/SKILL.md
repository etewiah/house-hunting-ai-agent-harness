---
name: run-house-hunt
description: Run the full house-hunting AI agent pipeline for a buyer brief — intake, ranking, explanation, comparison, and optional HomesToCompare link creation. No HTTP server or browser needed.
metadata:
  tags: house-hunt, harness, ranking, comparison, buyer-agent
---

# Run House Hunt Skill

Run the full buyer-agent pipeline from a plain-English brief: parse preferences, rank listings, explain matches, and optionally create a side-by-side comparison on HomesToCompare.

## Prerequisites (check before running)

- Python 3.10+ and `uv`
- Run commands from the harness root
- Environment variables exported in the shell if needed (see `.env.example`; this repo does not auto-load `.env`)
- For AI-powered intake and explanations: `ANTHROPIC_API_KEY`
- For HomesToCompare comparison creation: `H2C_BASE_URL` and `H2C_API_KEY`

Verify keys:
```bash
env | grep -E "ANTHROPIC_API_KEY|H2C_BASE_URL|H2C_API_KEY" || echo "No optional keys exported"
```

## Your task

When the user invokes this skill:

### Step 1 — Identify the buyer brief

Extract it from the user's message. If none was given, ask for one. A good brief includes:
- Location or commute destination
- Budget (e.g. £650k)
- Bedrooms (e.g. 3-bed)
- Key priorities (garden, quiet street, schools, parking, etc.)

Example: `"3-bed near Surbiton, budget £650k, max 45 min commute to Waterloo, need a garden"`

### Step 2 — Run the pipeline

Call the orchestrator directly via Python (run from the harness root directory):

> **Note:** Use `uv run --extra dev` so the repo dependencies are available without separately installing the package.

```bash
uv run --extra dev python - <<'EOF'
from src.app import build_app

brief = "BRIEF_GOES_HERE"

app = build_app()
profile = app.intake(brief)
ranked = app.triage(limit=5)
explanations = app.explain_top_matches()
comparison = app.compare_top(count=min(3, len(ranked)))
next_steps = app.prep_next_steps()

print("## Profile")
print(f"  Location: {profile.location_query}")
print(f"  Budget:   £{profile.max_budget:,}")
print(f"  Bedrooms: {profile.min_bedrooms}+")
if profile.max_commute_minutes:
    print(f"  Commute:  {profile.max_commute_minutes} min max")
print(f"  Must-haves: {', '.join(profile.must_haves) or 'none'}")

print("\n## Ranked listings")
for i, item in enumerate(ranked, 1):
    listing = item.listing
    print(
        f"  {i}. {listing.title}  [{item.score:.0f}/100]  "
        f"£{listing.price:,}  {listing.bedrooms}bed  {listing.location}"
    )
    if item.warnings:
        print(f"     ! {', '.join(item.warnings)}")

print("\n## Explanations")
for explanation in explanations:
    print(f"  {explanation}")

print("\n## Comparison")
print(comparison)

affordability = next_steps["affordability"]
print("\n## Affordability estimate")
print(f"  Deposit:  £{affordability.deposit:,}")
print(f"  Loan:     £{affordability.loan_amount:,}")
print(f"  Monthly:  ~£{affordability.monthly_payment:,}/month")
print(f"  Note:     {affordability.assumptions[-1]}")

print(f"\n{next_steps['boundary']}")

trace = app.tracer.flush("skill-run")
print(f"\nTrace: {trace}")
EOF
```

Replace `BRIEF_GOES_HERE` with the actual buyer brief.

### Step 3 — Optionally create a HomesToCompare comparison

If `H2C_BASE_URL` and `H2C_API_KEY` are exported, call `create_comparison()`:

```bash
uv run --extra dev python - <<'EOF'
import os

from src.app import build_app
from src.connectors.homestocompare_connector import HomesToCompareConnector

brief = "BRIEF_GOES_HERE"
base_url = os.environ.get("H2C_BASE_URL")
api_key = os.environ.get("H2C_API_KEY")

connector = HomesToCompareConnector(base_url=base_url, api_key=api_key) if base_url and api_key else None
app = build_app()
app.h2c_connector = connector

app.intake(brief)
app.triage(limit=5)
result = app.create_comparison(count=2)

if result.get("success") or result.get("comparison_url") or result.get("share_url"):
    print(f"Comparison URL: {result.get('comparison_url') or result.get('share_url')}")
else:
    print(f"Skipped: {result.get('reason', result)}")
EOF
```

### Step 4 — Export results (optional)

```bash
uv run house-hunt demo --export-path results.csv
uv run house-hunt demo --export-path results.html
```

Or via Python, pass `ExportOptions` directly to `app.export()`.

### Step 5 — Report back

Show the user:
- The parsed **BuyerProfile** (confirm the brief was understood correctly)
- The **ranked listing table** (title, score, price, location, warnings)
- The **comparison summary** (top 3 head-to-head)
- The **affordability estimate** for the top match (monthly payment, deposit, loan)
- The **HomesToCompare URL** if a comparison was created
- The **trace file path** for inspection

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: src` | Not running from harness root | `cd house-hunting-ai-agent-harness` first |
| `No listings matched` | Location query too specific for mock data | Try London/King's Cross, Manchester, Bristol, or Leeds examples |
| `LLM adapter not available` | `ANTHROPIC_API_KEY` not set | Falls back to regex intake automatically |
| `HomesToCompare connector not configured` | `H2C_BASE_URL` or `H2C_API_KEY` missing | Export both variables or skip comparison creation |
| `Both listings must have source_url` | Mock listings use demo URLs | Expected in demo mode — real listings from `H2CListingConnector` have live URLs |

## Key files

| File | Purpose |
|---|---|
| `src/app.py` | `build_app()` — wires config, LLM, listings, orchestrator |
| `src/harness/orchestrator.py` | Full pipeline: intake → triage → explain → compare → create_comparison |
| `src/skills/intake.py` | Brief → BuyerProfile (regex or LLM) |
| `src/skills/ranking.py` | Score listings against profile |
| `src/connectors/homestocompare_connector.py` | POST to HomesToCompare comparison API |
| `evals/datasets/listings_small.jsonl` | Mock listing data across London, Manchester, Bristol, and Leeds |
| `.env.example` | All supported environment variables |
