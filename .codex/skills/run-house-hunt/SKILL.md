---
name: run-house-hunt
description: Run the full house-hunting AI agent pipeline for a buyer brief — intake, ranking, explanation, comparison, affordability, and tour prep. Requires a configured listing provider or explicitly supplied listings.
metadata:
  tags: house-hunt, harness, ranking, comparison, buyer-agent
---

# Run House Hunt Skill

Run the full buyer-agent pipeline from a plain-English brief: parse preferences, rank listings, explain matches, compare homes, and prepare next steps.

## Prerequisites (check before running)

- Python 3.10+ and `uv`
- Run commands from the harness root
- No model provider key is required when an LLM agent is using this skill; the agent supplies the reasoning. If `ANTHROPIC_API_KEY` is exported, the standalone harness may use its optional Anthropic adapter for intake and explanations.
- A listing provider is required. Set `H2C_READ_KEY` for HomesToCompare search, set `LISTINGS_CSV_PATH` for an explicit CSV export, or normalize user-provided listings into `Listing` objects and run the individual skills.

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

### Step 3 — Export results (optional)

Via Python, pass `ExportOptions` directly to `app.export()` after ranking results.

### Step 4 — Report back

Show the user:
- The parsed **BuyerProfile** (confirm the brief was understood correctly)
- The **ranked listing table** (title, score, price, location, warnings)
- The **comparison summary** (top 3 head-to-head)
- The **affordability estimate** for the top match (monthly payment, deposit, loan)
- The **trace file path** for inspection

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: src` | Not running from harness root | `cd house-hunting-ai-agent-harness` first |
| `No listing provider configured` | Neither `H2C_READ_KEY` nor `LISTINGS_CSV_PATH` is set | Configure HomesToCompare search or pass an explicit CSV export |
| `No listings matched` | The configured provider returned no candidates | Relax the brief or inspect provider/API filters |
| Regex-style intake/explanations | No standalone harness LLM adapter configured | Expected for agent-driven use; the calling LLM agent can interpret and summarize results |

## Key files

| File | Purpose |
|---|---|
| `src/app.py` | `build_app()` — wires config, LLM, listings, orchestrator |
| `src/harness/orchestrator.py` | Full pipeline: intake → triage → explain → compare → next steps |
| `src/skills/intake.py` | Brief → BuyerProfile (regex or LLM) |
| `src/skills/ranking.py` | Score listings against profile |
| `.env.example` | All supported environment variables |
