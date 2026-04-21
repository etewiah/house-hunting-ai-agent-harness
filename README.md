# House Hunting Agent

Tell it what you want in plain English. Get ranked matches, explanations, an affordability estimate, and a list of questions to ask on the tour.

```
Your brief: 3-bed near Manchester Piccadilly, budget £350k, need a garden, max 30 min commute

Here's what I understood:
  Location:      Manchester commute
  Budget:        £350,000
  Bedrooms:      3+
  Commute:       30 mins max
  Must-haves:    garden

Does that look right? [Y/n]:
```

```
Found 3 matches:

1. Quiet Garden Terrace  [94/100]
   Walthamstow · £675,000 · 3 bed · 1 bath · 38 min commute
   + within budget, bedroom requirement, commute requirement, garden, walkable, quiet

Affordability estimate (top match):
  Deposit:  £101,250
  Loan:     £573,750
  Monthly:  ~£3,438/month
  Note: estimated mortgage payment only; excludes fees, taxes, insurance

Questions to ask on the tour:
  • What is included in the sale and what is excluded?
  • Have there been any recent repairs, disputes, or insurance claims?
  • What is the garden orientation and drainage like after heavy rain?
```

---

## For buyers: get started in 2 minutes

**Prerequisite:** install [uv](https://docs.astral.sh/uv/getting-started/installation/) (a fast Python package manager).

```bash
# clone the repo
git clone https://github.com/your-org/house-hunting-ai-agent-harness
cd house-hunting-ai-agent-harness

# run — no setup step needed
uv run house-hunt
```

Type your search in plain English when prompted. Include as much or as little as you like:

- `"3-bed in Bristol, budget £400k, need parking and good schools"`
- `"2-bed flat, max 20 min commute to London Bridge, under £500k"`
- `"somewhere quiet in Leeds with a garden, 4 beds, around £300k"`

The agent parses your brief, ranks the listings, shows you why each one matched or missed, estimates your monthly mortgage, and gives you tour questions.

> **Note:** listings in this demo are mock data. To search real listings, add a connector — see [Connecting real listings](#connecting-real-listings) below.

---

## What it produces

For each search the agent outputs:

| Output | What it tells you |
|---|---|
| Ranked matches | Listings scored against your brief, highest first |
| Match explanation | Exactly which requirements each listing met or missed |
| Side-by-side comparison | Beds, baths, price, commute, features in one view |
| Affordability estimate | Deposit, loan, and estimated monthly payment |
| Tour questions | Property-specific questions to ask the agent or vendor |
| Offer brief | Summary to share with your solicitor or broker |

Every figure is labelled as `listing_provided`, `estimated`, `inferred`, or `missing` so you always know what to verify.

---

## For developers: build on it

### Run the tests

```bash
uv run --extra dev pytest
```

### Project layout

```
src/
  skills/       intake, ranking, explanation, comparison, affordability, tour prep, offer brief
  harness/      orchestration, session state, policies, tracing, approvals
  connectors/   mock API, local CSV, MCP stub, HomesToCompare connector
  ui/           CLI, web demo stub
evals/
  tests/        eval suite
  datasets/     mock listing fixtures
```

### Connecting real listings

Implement the `search(profile: BuyerProfile) -> list[Listing]` interface in `src/connectors/` and pass it to `HouseHuntOrchestrator`. The mock connector in `src/connectors/mock_listing_api.py` is the reference implementation.

### Swapping in an LLM for intake

`parse_buyer_brief()` in `src/skills/intake.py` accepts an optional `llm` adapter. Pass any object with a `generate(prompt, model) -> str` method to use an LLM for richer brief parsing instead of regex.

### Trust model

Every factual output should carry one of these labels:

- `listing_provided` — came directly from the listing data
- `user_provided` — came from the buyer's brief
- `estimated` — calculated from stated assumptions
- `inferred` — derived, not directly stated
- `missing` — not available

The agent will never present itself as a lawyer, mortgage adviser, surveyor, inspector, or fiduciary buyer's agent.

---

## v0.1 scope

Included: CLI, mock listings, buyer intake, ranking, explanations, comparison, affordability estimate, tour prep, offer brief, eval suite, MCP connector stub.

Not included: live listing feeds, autonomous browsing, outbound calls, negotiation automation, legal or mortgage advice, transaction management.
