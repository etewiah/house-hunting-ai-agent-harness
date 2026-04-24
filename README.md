# House Hunting Agent

House Hunting Agent is a Python harness for buyer-side property workflows. A coding
agent, MCP client, or integration supplies a buyer brief plus candidate listings; the
harness parses the brief, ranks the listings, explains trade-offs, estimates affordability,
and prepares tour questions.

```
Buyer brief: 3-bed near Manchester Piccadilly, budget £350k, need a garden, max 30 min commute
Candidate listings: supplied by browser search, CSV, HomesToCompare, or another adapter

Here's what I understood:
  Location:      Manchester Piccadilly
  Budget:        £350,000
  Bedrooms:      3+
  Commute:       30 mins max
  Must-haves:    garden
```

```
Found 3 matches:

1. Ancoats Garden Townhouse  [94/100]
   Ancoats, Manchester · £345,000 · 3 bed · 2 bath · 18 min commute
   + within budget, bedroom requirement, commute requirement, garden

Affordability estimate (top match):
  Deposit:  £51,750
  Loan:     £293,250
  Monthly:  ~£1,758/month
  Note: estimated mortgage payment only; excludes fees, taxes, insurance

Questions to ask on the tour:
  • What is included in the sale and what is excluded?
  • Have there been any recent repairs, disputes, or insurance claims?
  • What is the garden orientation and drainage like after heavy rain?
```

---

## Using With Coding Agents

The harness is designed so coding agents such as [Codex](https://openai.com/codex) or [Claude Code](https://www.anthropic.com/claude-code) can use it
directly from the repository. An agent can read the docs, inspect the Python modules, run
the MCP server when needed, call functions from `src/skills/`, and run the eval suite without any server
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
- `docs/mcp-usage.md` — optional MCP server usage guide
- `.pi/extensions/house-hunt-browser/README.md` — Pi extension details
- `.pi/skills/browser-house-hunt/SKILL.md` — Pi skill instructions

## Using With Pi

This repo now has a project-local [Pi coding agent](https://www.npmjs.com/package/@mariozechner/pi-coding-agent) skill and Pi extension for browser-assisted house hunting.

### What Pi can do here

When you run [Pi coding agent](https://www.npmjs.com/package/@mariozechner/pi-coding-agent) inside this repo, it can:
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
| `uv run house-hunt serve` | Starts the optional MCP server |
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
uv run --extra dev pytest
```

The old standalone interactive listing search has been removed because it could not
discover live listings without an external provider. In coding-agent workflows, an agent
such as [Pi coding agent](https://www.npmjs.com/package/@mariozechner/pi-coding-agent),
[Claude Code](https://www.anthropic.com/claude-code), or [Codex](https://openai.com/codex)
finds or receives listings, normalizes them into `Listing` objects, and passes them into
the harness for ranking, comparison, explanation, and export.

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
  ui/           MCP/trace command utilities, web demo stub
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

For a dedicated MCP walkthrough, see `docs/mcp-usage.md`.

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

Included: buyer intake, ranking, explanations, comparison, affordability estimate, tour prep, offer brief, CSV/HTML export, eval suite, optional MCP server, trace utilities, connector stubs, and browser-assisted workflows via agent integrations such as [Pi coding agent](https://www.npmjs.com/package/@mariozechner/pi-coding-agent), [Claude Code](https://www.anthropic.com/claude-code), and [Codex](https://openai.com/codex).

Not included in the core harness: a built-in standalone autonomous browser agent, negotiation automation, legal or mortgage advice, transaction management.
