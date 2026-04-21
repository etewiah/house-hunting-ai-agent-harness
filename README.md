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

## Using With Coding Agents

The harness is designed so coding agents such as Codex or Claude Code can use it
directly from the repository. An agent can read the docs, inspect the Python modules, run
the CLI, call functions from `src/skills/`, and run the eval suite without any server
setup.

For agent-facing instructions, see [AGENTS.md](AGENTS.md).

Useful direct entry points:

| Entry point | What it does |
|---|---|
| `uv run house-hunt demo` | Runs the built-in demo dataset |
| `uv run house-hunt demo --export-path report.html` | Writes a self-contained HTML report |
| `uv run house-hunt demo --export-path shortlist.csv` | Writes a CSV shortlist |
| `uv run --extra dev pytest` | Runs the eval suite |
| `src/skills/*` | Repo-native skills for intake, ranking, comparison, exports, and next steps |
| `src/models/capabilities.py` | Provider-facing protocols for optional adapters |

Example prompt to a coding agent:

> Use this repo directly. Search or ingest candidate listings, normalize them into
> `Listing` objects, rank them against my brief, then export the result to HTML.

The agent retrieves or receives listings; the harness ranks, compares, exports, and
prepares next steps.

---

## Getting started

**Prerequisite:** install [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/your-org/house-hunting-ai-agent-harness
cd house-hunting-ai-agent-harness
uv run house-hunt
```

**With an Anthropic API key** (`ANTHROPIC_API_KEY` set in your environment), the CLI uses Claude for intake and explanations — it understands natural language properly and gives conversational, specific explanations for each match.

**Without a key**, it falls back to regex parsing and mock listings — useful for testing but not a real product experience.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uv run house-hunt
```

Type your search in plain English:

- `"3-bed in Bristol, budget £400k, need parking and good schools"`
- `"2-bed flat, max 20 min commute to London Bridge, under £500k"`
- `"somewhere quiet in Leeds with a garden, 4 beds, around £300k"`

> **Note:** the built-in listing dataset is mock data across London, Manchester, Bristol,
> and Leeds. For live listings, connect a listing connector, import CSV data, or have an
> agent normalize retrieved listings into `Listing` objects.

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
  connectors/   mock API, local CSV, optional MCP stub, HomesToCompare connector
  ui/           CLI, web demo stub
evals/
  tests/        eval suite
  datasets/     mock listing fixtures
```

### Connecting real listings

Implement the `search(profile: BuyerProfile) -> list[Listing]` interface in `src/connectors/` and pass it to `HouseHuntOrchestrator`. The mock connector in `src/connectors/mock_listing_api.py` is the reference implementation.

### Optional MCP server

The MCP server is optional. It is useful for clients that need MCP tool discovery and
tool calls, but coding agents can usually use the repo directly.

To start it manually:

```bash
uv run house-hunt serve
```

If your client requires static MCP config, add something like this to its configuration:

```json
{
  "mcpServers": {
    "house-hunt": {
      "command": "uv",
      "args": ["run", "house-hunt", "serve"],
      "cwd": "/path/to/house-hunting-ai-agent-harness"
    }
  }
}
```

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

Included: CLI, mock listings, buyer intake, ranking, explanations, comparison, affordability estimate, tour prep, offer brief, CSV/HTML export, eval suite, optional MCP server, and connector stubs.

Not included: live listing feeds, autonomous browsing, outbound calls, negotiation automation, legal or mortgage advice, transaction management.
