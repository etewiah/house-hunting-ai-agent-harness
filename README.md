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
For Codex skill discovery, see [.codex/skills/run-house-hunt/SKILL.md](.codex/skills/run-house-hunt/SKILL.md).
For a consolidated browser-first progress + usage guide, see [docs/browser-assisted-guide.md](docs/browser-assisted-guide.md).
For a chronological browser-first change log, see [docs/browser-assisted-changelog.md](docs/browser-assisted-changelog.md).

## Documentation

Key docs:
- `docs/README.md` — documentation map
- `docs/browser-assisted-guide.md` — browser-first and Pi usage guide
- `docs/browser-assisted-changelog.md` — chronological change log
- `.pi/extensions/house-hunt-browser/README.md` — Pi extension details
- `.pi/skills/browser-house-hunt/SKILL.md` — Pi skill instructions

## Using With Pi

This repo now has a project-local Pi skill and Pi extension for browser-assisted house hunting.

### What Pi can do here

When you run Pi inside this repo, it can:
- search the web for listing URLs
- extract listing pages into normalized data
- attach extraction diagnostics and quality scores
- heuristically enrich missing commute times
- run the Python harness on browser-found or user-supplied listings
- export results to HTML and CSV

### Pi quick start

Start Pi in this repo, then run:

```text
pi
/reload
/skill:browser-house-hunt
```

Fastest path:
- use `house_hunt_from_web` for the one-shot browser flow

More controlled path:
- `property_web_search`
- `extract_property_listings`
- `run_house_hunt_harness`

Smoke test command:

```text
/house-hunt-smoke 2-bed flat near Birmingham New Street, under £250k, parking preferred
```

Pi-specific docs:
- `.pi/extensions/house-hunt-browser/README.md`
- `.pi/skills/browser-house-hunt/SKILL.md`
- `docs/browser-assisted-guide.md`
- `docs/browser-assisted-changelog.md`

Useful direct entry points:

| Entry point | What it does |
|---|---|
| `uv run house-hunt` | Starts an interactive CLI; direct search requires a configured listing provider |
| `uv run --extra dev pytest` | Runs the eval suite |
| `.codex/skills/run-house-hunt/SKILL.md` | Codex skill for running the full buyer brief pipeline |
| `src/skills/*` | Repo-native skills for intake, ranking, comparison, exports, and next steps |
| `src/models/capabilities.py` | Provider-facing protocols for optional adapters |

Example prompt to a coding agent:

> Use this repo directly. Search or ingest candidate listings, normalize them into
> `Listing` objects, rank them against my brief, then export the result to HTML.

The agent retrieves or receives listings; the harness ranks, compares, exports, and
prepares next steps.

In browser-assisted Pi workflows, extracted listings can also carry extraction-quality
metadata and heuristic commute estimates so downstream ranking and exports remain honest
about what was scraped vs estimated.

---

## Getting started

**Prerequisite:** install [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/your-org/house-hunting-ai-agent-harness
cd house-hunting-ai-agent-harness
uv run house-hunt
```

**With an Anthropic API key** (`ANTHROPIC_API_KEY` set in your environment), the CLI uses Claude for intake and explanations — it understands natural language properly and gives conversational, specific explanations for each match.

The standalone CLI needs a listing provider for direct search. Set `H2C_READ_KEY` for HomesToCompare search, or
set `LISTINGS_CSV_PATH` to a CSV export with `Listing` fields. In coding-agent workflows,
the listing provider is optional: the agent can find listings with browser tools or other
sources, normalize them into `Listing` objects, and pass them into the harness for ranking,
comparison, explanation, and export. Without an LLM key, intake falls back to regex parsing.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uv run house-hunt
```

Type your search in plain English:

- `"3-bed in Bristol, budget £400k, need parking and good schools"`
- `"2-bed flat, max 20 min commute to London Bridge, under £500k"`
- `"somewhere quiet in Leeds with a garden, 4 beds, around £300k"`

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
  connectors/   local CSV, optional MCP stub, HomesToCompare connector
  ui/           CLI, web demo stub
evals/
  tests/        eval suite
  datasets/     buyer profile and comparison fixtures
```

### Connecting real listings

Implement the `search(profile: BuyerProfile, limit: int = 200) -> list[Listing]`
interface in `src/connectors/` and pass it to `HouseHuntOrchestrator`. Existing
examples are `H2CListingConnector` and `LocalCsvListingConnector`.

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

Included: CLI, buyer intake, ranking, explanations, comparison, affordability estimate, tour prep, offer brief, CSV/HTML export, eval suite, optional MCP server, and connector stubs.

Not included: autonomous browsing, negotiation automation, legal or mortgage advice, transaction management.
