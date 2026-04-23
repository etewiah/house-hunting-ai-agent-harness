# Claude Code Parity Plan

This document describes, in detail, how to bring the Claude Code integration in
this repository up to the same level of capability that the Pi integration
already has. It is organized as a plan rather than a changelog: each tier
explains the intent, the exact file artifacts, and the acceptance criteria
needed to consider that tier complete.

It is a *plan* doc. No code has been written for any of the tiers described
here yet. Nothing in this document should be treated as already implemented.

## Who this is for

Read this if you want to:

- understand why the Claude Code surface of this repo feels thinner than the
  Pi surface
- see exactly which files need to exist for Claude Code to reach parity
- decide how much of that work to do, and in what order
- hand the plan to a contributor or agent to implement

Everything here is scoped to the Claude Code side. Pi behavior is only
referenced for context; no changes to `.pi/` are proposed by this plan.

## Background

### What Pi currently provides

The Pi integration in this repo is made up of four independently useful
layers:

1. **A rich skill** at `.pi/skills/browser-house-hunt/SKILL.md` which teaches
   Pi how to drive the full "discover on the web, normalize, rank with the
   harness" workflow end to end, including a normalized listing schema, a
   step-by-step workflow, guardrails, and troubleshooting guidance.
2. **A project-local Pi extension** at `.pi/extensions/house-hunt-browser/`
   that registers five first-class tools and one slash command:
   - `property_web_search` — DuckDuckGo HTML results filtered to
     Rightmove / Zoopla / OnTheMarket.
   - `property_listing_extract` — fetches one listing page and runs
     site-specific parsers with JSON-LD fallbacks, producing a normalized
     listing *and* extraction diagnostics (parser used, field provenance,
     quality score, missing fields, warnings).
   - `extract_property_listings` — the same, in batch.
   - `run_house_hunt_harness` — shells into the Python helper script
     `.pi/skills/browser-house-hunt/run_house_hunt.py` and returns its output.
   - `house_hunt_from_web` — the end-to-end flow: search → extract → commute
     enrichment → quality filter → harness run.
   - `/house-hunt-smoke <brief>` — a slash command that drives
     `house_hunt_from_web` with defaults and formats a summary.
3. **Extraction quality machinery** — per-field provenance, a 0–100 quality
   score, missing-field reporting, and a configurable minimum-quality gate
   before ranking.
4. **Heuristic commute enrichment** — inferring a commute destination from
   the brief or an explicit parameter, and stamping commute estimates onto
   listings marked as estimated so downstream outputs can be honest about
   provenance.
5. **Fixture-backed tests** — an HTML fixture corpus under
   `.pi/extensions/house-hunt-browser/test/` and a Node-based test runner
   covering the extractor, normalization, and commute logic.

### What the Claude Code side currently provides

The Claude Code surface of this repo is a single folder:

```
.claude/
  skills/
    run-house-hunt/
      SKILL.md
```

That skill runs `build_app()` inline in a single Python heredoc and prints a
profile, ranked listings, comparison, and affordability estimate. There is:

- no `.claude/settings.json` wiring
- no `.mcp.json` registering the repo's existing MCP server
- no slash command definition
- no browser-first skill
- no subagent definitions
- no tool-level wiring for `WebSearch`, `WebFetch`, or the `claude-in-chrome`
  MCP tools

The Python MCP server at `src/ui/mcp_server.py` already exposes nine useful
tools (`parse_brief`, `rank_listings`, `run_house_hunt`, `compare_homes`,
`estimate_affordability`, `tour_questions`, `offer_brief`, `export_csv`,
`export_html`), but no file in `.claude/` or at the repo root tells Claude
Code to start it.

### Side-by-side capability comparison

| Capability                                | Pi             | Claude Code today | Gap                         |
|-------------------------------------------|----------------|-------------------|-----------------------------|
| Runs the Python harness                   | Yes            | Yes (via skill)   | none                        |
| Web search for listings                   | Yes            | Only via generic `WebSearch`, not a first-class harness tool | medium |
| Page extraction with site-specific parsers | Yes           | No                | high                        |
| Extraction quality scoring + filtering    | Yes            | No                | high                        |
| Commute enrichment                        | Yes (heuristic)| No                | high                        |
| End-to-end discover→rank tool             | Yes (`house_hunt_from_web`) | No     | high                        |
| Slash command for smoke test              | Yes (`/house-hunt-smoke`) | No      | low                         |
| Rich browser skill doc                    | Yes            | No                | low                         |
| MCP server auto-registered                | n/a            | No                | low                         |
| Subagent for extraction                   | n/a            | No                | low                         |
| Fixture-backed parser tests               | Yes            | No (would inherit from port) | medium            |

## Design principle

Claude Code already has native primitives that line up well with Pi's
extension points. Parity does **not** require re-porting everything.

| Pi primitive                 | Claude Code equivalent                           | Notes |
|------------------------------|---------------------------------------------------|-------|
| Project extension tool       | MCP server tool                                   | Register via `.mcp.json` or `.claude/settings.json`. |
| Extension slash command      | `.claude/commands/<name>.md` markdown command     | Body is prompt-executed by Claude Code. |
| Project skill                | `.claude/skills/<name>/SKILL.md`                  | Same SKILL.md YAML front-matter format. |
| Generic web search           | Built-in `WebSearch` tool                         | No port needed. |
| Generic page fetch           | Built-in `WebFetch` tool                          | Good enough for a Tier-1 flow; weaker than Pi's site-specific parsers. |
| Browser-driven fetch         | `claude-in-chrome` MCP (`navigate`, `read_page`)  | Optional upgrade over `WebFetch`. |
| Subprocess call back to repo | Same `uv run` invocations or a new MCP tool       | Can reuse Pi's Python runner script. |

The plan below leans into these equivalents, so Tier 1 is *mostly wiring*,
Tier 2 is the real engineering (porting the extractors), and Tier 3 is
polish.

## Tier 1 — Wiring parity

**Goal:** give Claude Code access to the repo's existing harness through MCP
and teach it the same high-level workflow Pi has, using Claude Code's native
web tools for discovery. Should be achievable in well under a day.

### Tier 1 artifacts (complete list)

| Path                                                        | Purpose                                             |
|-------------------------------------------------------------|-----------------------------------------------------|
| `.mcp.json`                                                 | Register the `house-hunt` MCP server with Claude Code. |
| `.claude/skills/browser-house-hunt/SKILL.md`                | New browser-first skill mirroring the Pi skill.     |
| `.claude/commands/house-hunt-smoke.md`                      | Slash command counterpart to `/house-hunt-smoke`.   |
| `.claude/settings.json` *(optional)*                        | Project-level permission allowlist for the harness. |
| `docs/claude-integration-guide.md` *(optional, follow-up)*  | User-facing "how do I use this with Claude Code" doc. |
| Index update in `docs/README.md`                            | Link the new doc + surfaces the Claude Code surface. |

### 1.1 Register the MCP server

The repo already ships a ready-to-use MCP server. The only thing missing is
the file that tells Claude Code to start it when it opens this project.

There are two acceptable locations; pick one and be consistent.

**Option A — `.mcp.json` at the repo root (recommended).**

```json
{
  "mcpServers": {
    "house-hunt": {
      "command": "uv",
      "args": ["run", "house-hunt", "serve"],
      "cwd": "${workspaceFolder}",
      "env": {}
    }
  }
}
```

Rationale:

- `.mcp.json` is Claude Code's standard per-project MCP registry. It is
  picked up automatically.
- It keeps MCP wiring separate from hooks, permissions, and env overrides,
  which belong in `.claude/settings.json`.
- Other MCP-capable clients (for example an IDE) can reuse the same file.

**Option B — inline under `.claude/settings.json`.**

```json
{
  "mcpServers": {
    "house-hunt": {
      "command": "uv",
      "args": ["run", "house-hunt", "serve"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

Use this only if you also want to co-locate Claude-specific hooks,
permissions, or status-line configuration in the same file. Mixing the two
is legal but makes the settings file larger and harder to diff.

**Note on `cwd`.** The MCP server imports `src.*`, so it must start from
the harness root. `${workspaceFolder}` resolves to the repo root in Claude
Code; leave it as-is.

**Do not put secrets in either file.** The CLAUDE.md at the workspace root
forbids touching `.env`. MCP registration does not need any secret: the
harness reads env vars from the already-loaded `.env` at runtime.

### 1.2 Add `.claude/settings.json` (optional)

If you want the skill to be able to run `uv run …` and write trace files
without tripping permission prompts every time, add:

```json
{
  "permissions": {
    "allow": [
      "Bash(uv run:*)",
      "Bash(mkdir -p .tmp)",
      "Bash(python .pi/skills/browser-house-hunt/run_house_hunt.py:*)",
      "Write(.tmp/*)"
    ]
  }
}
```

This is optional; skip it if you prefer to approve commands interactively.
It is also the right place for a future status-line entry or hooks.

### 1.3 Add the browser-first Claude skill

Create `.claude/skills/browser-house-hunt/SKILL.md`. The body should mirror
the Pi skill but be rewritten against Claude Code primitives.

Recommended structure (do not copy verbatim; adapt to project style):

```markdown
---
name: browser-house-hunt
description: Find property listings with WebSearch/WebFetch (or claude-in-chrome MCP tools), normalize them into Listing-shaped dicts, and run the house-hunting harness via the `house-hunt` MCP server. Use when a user wants real candidate properties ranked against a buyer brief.
metadata:
  tags: house-hunt, browser, listings, ranking, property
---

# Browser House Hunt (Claude Code)

Use this skill when the user wants help finding actual properties to buy or
rent and you have web or browser tools available in this Claude Code
session.

This skill treats **web discovery** and **harness evaluation** as separate
steps:

1. collect candidate listings using WebSearch / WebFetch / claude-in-chrome
2. normalize each listing into the repo's Listing shape
3. call the `run_house_hunt` MCP tool with the brief and listings
4. report ranked matches, explanations, comparison, affordability, tour
   questions, and offer prep

If the `house-hunt` MCP server is not loaded, say so and fall back to the
existing `run-house-hunt` skill (which calls `build_app()` directly).

## Tool preferences

Prefer, in order:

1. `run_house_hunt` (MCP) — one call, structured output
2. `rank_listings` + `compare_homes` + `estimate_affordability` + `offer_brief`
   (MCP) — more granular control
3. The existing `run-house-hunt` skill — fallback when MCP is unavailable

For discovery:

1. Claude Code's built-in `WebSearch` for candidate URLs
2. `WebFetch` or `claude-in-chrome` `navigate` + `read_page` for page content
3. Ask the user for listing URLs if web tools are unavailable or blocked

## Listing schema to normalize into

Reuse the same schema as the Pi skill:

<listing JSON example as in Pi skill>

Follow the same field rules: integer price/beds/baths, nullable commute,
normalized feature tokens, preserved `source_url`, and
`external_refs.extraction_*` for diagnostics if you generated any.

## Workflow

Mirror the Pi skill's five steps, but substitute:

- Pi's `property_web_search` → `WebSearch`
- Pi's `property_listing_extract` → `WebFetch` (Tier 1) or the Tier-2 MCP
  tool once it exists
- Pi's `run_house_hunt_harness` → the `run_house_hunt` MCP tool (or the
  existing `run-house-hunt` skill as a fallback)

## Guardrails

Same as the Pi skill: no legal / mortgage / survey / inspection /
negotiation advice, mark missing or estimated values, preserve source URLs,
never invent commute times.

## Troubleshooting

Use the same failure table as the Pi skill, plus:

| Problem | What to do |
|---|---|
| `house-hunt` MCP server not loaded | Verify `.mcp.json` exists and `uv run house-hunt serve` works from the repo root. |
| `WebFetch` blocked by a site | Try `claude-in-chrome` `navigate` + `read_page`, or ask the user to paste listing data. |
```

### 1.4 Add the slash command

Create `.claude/commands/house-hunt-smoke.md`. The body of the command is a
prompt that Claude executes when the user types `/house-hunt-smoke <brief>`.

```markdown
---
description: Smoke-test the browser-assisted house-hunt flow on a given buyer brief.
---

Run a smoke test of the browser-assisted house-hunt workflow on this brief:

$ARGUMENTS

Steps:

1. If `$ARGUMENTS` is empty, ask the user for a brief and stop.
2. Use WebSearch to find 5–8 candidate listings on rightmove.co.uk,
   zoopla.co.uk, or onthemarket.com that plausibly match the brief.
3. For each result, use WebFetch (or the `claude-in-chrome` MCP tools) to
   fetch the page and extract: id, title, price, bedrooms, bathrooms,
   location, commute_minutes (nullable), features, description, source_url.
4. Drop any listing where you could not get at least price, bedrooms, and
   location.
5. Call the `run_house_hunt` MCP tool with the brief and the normalized
   listings.
6. Summarize: buyer profile, top 5 ranked listings with score/price/beds/
   location/warnings, comparison, affordability for the top match, and the
   trace path returned by the tool.

Guardrails:

- Do not invent missing fields.
- Do not present outputs as legal, mortgage, survey, or negotiation advice.
- Mark estimated or missing values honestly.
```

### 1.5 Update the docs index

Add one bullet to `docs/README.md` under a new `Claude Code` subsection (or
under `Browser-first / Pi docs` if you prefer a single cross-client
section) pointing at this plan and, once it exists,
`docs/claude-integration-guide.md`.

### Tier 1 acceptance criteria

The tier is done when all of the following are true:

- [ ] Running `claude` in the repo root loads the `house-hunt` MCP server
      without manual configuration.
- [ ] Typing `/mcp` inside Claude Code lists `house-hunt` and all nine of
      its tools.
- [ ] The `browser-house-hunt` skill appears in the skills list and, when
      invoked with a brief, completes a full discover → rank → report
      cycle using `WebSearch` + `WebFetch` + `run_house_hunt`.
- [ ] `/house-hunt-smoke <brief>` runs to completion and produces a
      ranked summary with a trace path.
- [ ] The existing `run-house-hunt` skill still works unchanged as a
      no-browser fallback.
- [ ] Nothing in this tier required editing `.env`.

### Tier 1 known limitations

After Tier 1, Claude Code can *work* the same high-level flow as Pi, but:

- Extraction quality is whatever `WebFetch` can produce against the raw HTML.
  There are no Rightmove / Zoopla / OnTheMarket site-specific parsers on
  this path, so quality scores, field provenance, and missing-field
  diagnostics are absent.
- Commute enrichment is whatever the language model can infer from the
  brief and page text; there is no heuristic commute engine.
- There is no `house_hunt_from_web`-equivalent end-to-end MCP tool; the
  sequencing lives in the skill and the slash command instead.

Tier 2 is the fix for all three.

## Tier 2 — Extraction parity

**Goal:** expose the same site-specific extraction quality Pi has through
MCP, so Claude Code (or any MCP client) can get the same structured
diagnostics without depending on Claude's generic `WebFetch`.

### Scoping decision: Python port vs Node subprocess

The Pi extension's parser core is in three `.mjs` files:

- `extractor-core.mjs`
- `commute-core.mjs`
- `normalization-core.mjs`

There are two reasonable strategies.

**Strategy A — Port to Python.**

Rewrite the three `.mjs` files as Python modules under
`src/skills/extraction/` and `src/skills/commute/`, then expose them as
MCP tools. Advantages:

- One language across the harness.
- Easier to add to the Python test suite.
- No Node runtime required at MCP-call time.

Disadvantages:

- Two implementations to keep in sync with the Pi extension, which will
  drift.
- Regex and JSON-LD walk logic must be reimplemented carefully to match
  quality scores.

**Strategy B — Shell out to Node from a Python MCP tool.**

Keep the `.mjs` files canonical under `.pi/extensions/house-hunt-browser/`
and wrap them with a small Node CLI that accepts stdin HTML and returns
JSON on stdout. The new Python MCP tools call that CLI via `subprocess`.

Advantages:

- One source of truth for parser logic.
- Bug fixes to the parser benefit both Pi and Claude Code immediately.

Disadvantages:

- Requires Node to be installed on machines running the MCP server.
- Adds process-boundary overhead per extraction.
- The extension folder becomes load-bearing for the Claude Code path, which
  makes it harder to delete or relocate later.

**Recommendation:** Strategy B first. It preserves a single source of truth
for parser behavior and it takes far less work than a careful Python port.
Move to Strategy A only if Node becomes a deployment blocker or if the
parser logic stabilizes enough that dual-maintenance becomes cheap.

### Tier 2 artifacts

| Path                                                        | Purpose                                             |
|-------------------------------------------------------------|-----------------------------------------------------|
| `.pi/extensions/house-hunt-browser/bin/extract-cli.mjs` *(new)* | Small CLI wrapper around `extractListingFromHtml`. |
| `.pi/extensions/house-hunt-browser/bin/commute-cli.mjs` *(new)* | CLI wrapper around `enrichListingsWithCommute`.    |
| `src/skills/browser_extraction.py` *(new)*                  | Python side that calls the Node CLI and returns dicts. |
| `src/ui/mcp_server.py` *(updated)*                          | Register four new MCP tools.                        |
| `evals/datasets/extraction_fixtures/` *(new)*               | Python-side fixtures mirroring the Node test fixtures. |
| `evals/tests/test_browser_extraction.py` *(new)*            | Python tests for the new MCP tools.                 |
| `docs/mcp-usage.md` *(updated)*                             | Document the four new MCP tools.                    |

### New MCP tool signatures

All four live in `src/ui/mcp_server.py` and are thin wrappers over
`src/skills/browser_extraction.py`. Signatures:

```python
@mcp.tool()
def property_web_search(
    query: str,
    max_results: int = 8,
    sites: list[str] | None = None,
) -> list[dict]:
    """Return candidate listing URLs + titles for a buyer brief."""

@mcp.tool()
def property_listing_extract(
    url: str,
    commute_minutes: int | None = None,
) -> dict:
    """Fetch one listing page and return normalized listing + diagnostics."""

@mcp.tool()
def extract_property_listings(
    urls: list[str],
    commute_minutes_by_url: dict[str, int] | None = None,
) -> dict:
    """Batch equivalent of property_listing_extract with a failure list."""

@mcp.tool()
def house_hunt_from_web(
    brief: str,
    max_results: int = 6,
    sites: list[str] | None = None,
    min_quality_score: int = 45,
    commute_destination: str | None = None,
    commute_mode: str = "transit",
    export_html_path: str | None = None,
    export_csv_path: str | None = None,
) -> dict:
    """Search, extract, enrich commute, filter by quality, then run the harness."""
```

Return payloads should mirror the Pi extension's return shape field for
field so that the existing `browser-house-hunt` skill on the Pi side can be
pointed at either backend in the future.

### Fetching model

For Tier 2, page fetching on the Python side should use a bounded
`urllib.request` or `httpx` call with:

- a user-agent string that identifies the harness (not a browser UA)
- a short timeout (for example 10s)
- a hard response-size cap
- no cookies, no redirects beyond a small limit
- no JavaScript execution

The extracted HTML is then piped into `extract-cli.mjs` which runs
`extractListingFromHtml` from the existing `.mjs` core. No changes to the
`.mjs` core are required for Tier 2.

### Update the Claude skill to prefer Tier 2 tools

Once Tier 2 lands, edit `.claude/skills/browser-house-hunt/SKILL.md` so its
"Tool preferences" section prefers:

1. `house_hunt_from_web` — end-to-end
2. `property_web_search` + `extract_property_listings` + `run_house_hunt`
   — granular control
3. `WebSearch` + `WebFetch` + `run_house_hunt` — fallback when the new
   tools are unavailable
4. The original `run-house-hunt` skill — final fallback

This matches the Pi skill's own preference ordering.

### Tier 2 acceptance criteria

- [ ] `uv run --extra dev pytest` exercises the four new MCP tools with at
      least one fixture per parser (Rightmove, Zoopla, OnTheMarket, generic).
- [ ] `/mcp` lists the four new tools.
- [ ] Running `house_hunt_from_web` on a live brief produces the same
      field-level provenance and quality score that the Pi extension
      produces for the same URL.
- [ ] The Claude `browser-house-hunt` skill prefers the Tier 2 tools when
      available and degrades cleanly when they are not.
- [ ] `docs/mcp-usage.md` lists the four new tools with argument tables
      and examples.

### Tier 2 risks

- **Node presence.** Contributors without Node installed cannot run the
  Tier 2 MCP tools. Mitigate with a clear error message in
  `browser_extraction.py` telling the user to install Node 20+.
- **Process startup cost.** Spawning Node per extraction adds latency.
  Mitigate with a small in-memory cache keyed by URL and a batch entry
  point (`extract_property_listings`) that spawns Node once per batch.
- **Parser drift.** If the `.mjs` core changes its output shape, the
  Python wrapper breaks. Mitigate with a single `schema_version` field in
  the CLI output and a JSON schema check in `browser_extraction.py`.

## Tier 3 — Polish

**Goal:** match Pi's test ergonomics and offer Claude Code-specific niceties.

### 3.1 Subagent for extraction

Add `.claude/agents/listing-extractor.md`. This is a specialized subagent
whose job is to take a list of listing URLs and return normalized listings
plus diagnostics, using the Tier 2 MCP tools. Running this work in a
subagent keeps the main conversation context clean when extracting many
pages.

Example front-matter:

```markdown
---
name: listing-extractor
description: Extract and normalize property listings from a list of URLs using the house-hunt MCP tools. Use when you need to process more than 3 listing URLs.
tools: [mcp__house-hunt__extract_property_listings, mcp__house-hunt__property_listing_extract]
---
```

Prompt body should instruct the subagent to batch where possible, skip
unreachable URLs, and return a compact JSON summary plus a failure list.

### 3.2 Parser evals on the Python side

Port (or reference) a subset of the Pi extension fixtures into
`evals/datasets/extraction_fixtures/` and write parser tests in
`evals/tests/test_browser_extraction.py` that:

- load the HTML fixture
- call `property_listing_extract` directly (in-process, not via MCP)
- assert that the normalized listing matches the expected shape
- assert that the quality score is above a per-fixture floor
- assert that `fieldSources` uses the expected per-field provenance

This gives the Python suite the same confidence level the Node suite has,
so regressions are caught on either side.

### 3.3 Optional: Claude Code-only status line

A trivial `.claude/settings.json` status line entry showing the current
brief and listing count can be added, but this is purely cosmetic and has
no parity impact.

### Tier 3 acceptance criteria

- [ ] `.claude/agents/listing-extractor.md` exists and can be invoked by
      the main agent to process a batch of URLs.
- [ ] Python parser tests pass under `uv run --extra dev pytest`.
- [ ] The extension-side Node tests and the Python-side parser tests both
      cover the same set of parsers (Rightmove, Zoopla, OnTheMarket,
      generic).

## End-state architecture

After all three tiers, the Claude Code surface of this repo looks like:

```
.mcp.json                                    # registers the house-hunt MCP server
.claude/
  settings.json                              # optional permissions + hooks
  skills/
    run-house-hunt/SKILL.md                  # unchanged, no-browser fallback
    browser-house-hunt/SKILL.md              # new, browser-first skill
  commands/
    house-hunt-smoke.md                      # new, slash command
  agents/
    listing-extractor.md                     # new, extraction subagent
```

On the Python side, the new pieces are:

```
src/
  skills/
    browser_extraction.py                    # calls Node CLI, returns dicts
  ui/
    mcp_server.py                            # +4 tools
evals/
  datasets/
    extraction_fixtures/                     # mirrors Node fixtures
  tests/
    test_browser_extraction.py
.pi/extensions/house-hunt-browser/
  bin/
    extract-cli.mjs                          # new CLI wrapper
    commute-cli.mjs                          # new CLI wrapper
```

Pi's existing extension stays authoritative for parser logic.

## Rollout plan

### Suggested PR sequence

1. **PR 1 — Tier 1 wiring.**
   - Add `.mcp.json`.
   - Add `.claude/settings.json` with permissions only, if desired.
   - Add `.claude/skills/browser-house-hunt/SKILL.md`.
   - Add `.claude/commands/house-hunt-smoke.md`.
   - Update `docs/README.md` and this doc.
   - No Python or TypeScript changes.
2. **PR 2 — Tier 2 CLI wrappers.**
   - Add `bin/extract-cli.mjs` and `bin/commute-cli.mjs` in the existing
     extension folder. Pure mechanical wrapping; no logic changes.
   - Add unit tests under `.pi/extensions/house-hunt-browser/test/` for the
     CLI contract (schema_version, stdout shape).
3. **PR 3 — Tier 2 Python integration.**
   - Add `src/skills/browser_extraction.py` and the four new MCP tools.
   - Add `evals/datasets/extraction_fixtures/` and
     `evals/tests/test_browser_extraction.py`.
   - Update the Claude skill to prefer the Tier 2 tools.
   - Update `docs/mcp-usage.md` and the browser-assisted guide.
4. **PR 4 — Tier 3 polish.**
   - Add `.claude/agents/listing-extractor.md`.
   - Optional status line and any other cosmetic niceties.

Each PR should be mergeable on its own.

### Validation per PR

- Run `uv run --extra dev pytest` and confirm no regressions.
- Run `cd .pi/extensions/house-hunt-browser && npm test` and confirm no
  regressions.
- From a fresh Claude Code session in the repo root, invoke
  `/house-hunt-smoke "2-bed flat near Birmingham New Street, under £250k"`
  and confirm:
  - MCP tools are listed.
  - The slash command runs end to end.
  - A ranked summary and trace path are produced.

## Security and compliance notes

- **Absolute `.env` protection.** None of the tiers require reading,
  writing, or touching `.env`. All MCP server wiring is done through
  non-secret config files. This is consistent with the workspace-level
  CLAUDE.md policy.
- **Paid AI inference.** None of the tiers call the paid endpoints listed
  in the workspace CLAUDE.md. If a future tier wants to use them, it must
  gate on `APPROVE_PAID_LLM_CALLS` and include the `x-llm-approval` /
  `x-ai-approval` header as required.
- **Listing sites' terms.** Both Pi's extension and the Tier 2 Python path
  fetch publicly reachable listing pages. Document in the browser-assisted
  guide that users are responsible for complying with the terms of service
  of any site they scrape, and that production deployments should prefer
  official listing APIs over HTML scraping.

## Open questions

1. **Should the `run-house-hunt` skill be deleted once the new browser skill
   exists?** Probably not: the no-browser fallback remains useful for
   sessions where web tools are denied or offline.
2. **Should Claude Code's built-in `WebFetch` be replaced by the Tier 2
   MCP tool inside the skill, even when the MCP tool is unavailable?** A
   pragmatic middle ground is: always prefer the MCP tool, but allow the
   skill to fall back to `WebFetch` when MCP is absent, and mark the
   resulting listings with a lower quality score so downstream ranking can
   see the difference.
3. **Should the MCP server gain a long-running mode?** Currently
   `uv run house-hunt serve` starts fresh per MCP session. If Claude Code
   is invoked frequently, a persistent daemon could reduce startup
   latency. This is an optimization and is out of scope for Tier 1–3.
4. **Do we want a Claude Code plugin?** A plugin would bundle `.mcp.json`,
   the skills, the commands, and the agents into a single installable
   unit. This is more useful for users of this harness in other
   repositories than for this repo itself, so it is deferred.

## Bottom line

- Claude Code does not need a ported TypeScript extension to reach parity
  with Pi. It needs wiring, a skill, a slash command, and, for full
  extraction parity, four new MCP tools that reuse the existing `.mjs`
  parser core via a small Node CLI.
- Tier 1 alone closes roughly 80% of the practical capability gap and can
  land in one mechanical PR. Tier 2 closes the quality gap on extraction.
  Tier 3 matches Pi's test ergonomics and adds Claude-specific niceties.
- Nothing in this plan touches `.env`, calls paid AI endpoints, or
  requires new secrets.
