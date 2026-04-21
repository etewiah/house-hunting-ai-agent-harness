# 02 — Richer AI-Powered Comparison

## Goal

The current `compare_homes` function in `src/skills/comparison.py` produces a bullet
list: price, beds, baths, commute, features. It gives the buyer raw facts but no
interpretation. A buyer who has told the harness they need a garden, hate long commutes,
and are stretching their budget still has to do the mental work of reading the bullet
list and deciding which trade-offs matter.

The goal is a narrative comparison that:

- Speaks to the buyer's stated priorities ("Listing A saves you £22k but has no garden,
  which you listed as a must-have")
- Quantifies trade-offs in buyer-relevant units (not just "Listing B has a longer
  commute" but "Listing B adds 18 minutes each way — roughly 2.5 hours a week")
- Calls out the single most important difference between each pair
- Is concise enough to read in 90 seconds — three short paragraphs maximum

This makes the harness genuinely useful to buyers who are making a high-stakes, high-
stress decision. It also creates a natural synergy with HomesToCompare: an AI-generated
narrative can be written directly to the H2C comparison page so the buyer has a
persistent, shareable version to send to their partner, solicitor, or mortgage broker.

---

## HomesToCompare Integration

The H2C comparison URL structure is `/pc/[suid_code]/overview` |
`/pc/[suid_code]/details` | `/pc/[suid_code]/for-the-ai`.

**The `/for-the-ai` endpoint is the critical integration point.**

This endpoint is designed to supply structured data about a comparison to an AI agent.
The plan is to make the relationship bidirectional:

1. **Read:** The harness calls `GET /pc/[suid_code]/for-the-ai` to get the full
   machine-readable comparison payload — listing attributes, any existing notes, prior
   AI analysis. This gives the LLM a richer context than the harness's own `Listing`
   objects, because H2C may hold additional fields (EPC rating, tenure, listing age,
   price history).

2. **Write:** After generating the narrative, the harness POSTs the narrative back to
   H2C via the existing `/api/house-hunt/create-comparison` endpoint (extended with a
   `narrative` field) or a new `/api/house-hunt/enrich-comparison` endpoint. The H2C
   comparison page then surfaces this narrative for users viewing the page directly.

3. **Shareable output:** `create_comparison` already returns a comparison URL. The
   richer comparison workflow returns the same URL but now the page at that URL also
   contains the AI narrative — giving buyers a link they can share that carries the
   reasoning, not just the data.

This makes H2C the persistence and sharing layer for AI-generated content, which is
a strong differentiator for H2C over plain listing aggregators.

---

## External APIs / Services

### Anthropic Messages API (Claude)
- SDK: `anthropic` Python package
- Models in use: `claude-haiku-4-5-20251001` (intake/explain), optionally
  `claude-sonnet-4-6` for deeper comparison reasoning
- Cost: Haiku ~$0.25/$1.25 per M input/output tokens. Sonnet ~$3/$15 per M.
  A 3-listing comparison prompt is roughly 1,500 tokens in + 400 out = ~$0.001 on
  Haiku, ~$0.011 on Sonnet.
- The `LlmAdapter` protocol in `src/skills/intake.py` already abstracts the provider,
  so OpenAI GPT-4o is a drop-in alternative.

### OpenAI Chat Completions API (alternative)
- Model: `gpt-4o` or `gpt-4o-mini`
- Already supported via `src/connectors/openai_adapter.py`
- Cost: GPT-4o-mini ~$0.15/$0.60 per M tokens; approximately the same cost tier as
  Claude Haiku for this workload.

No additional external services are required — the comparison is a pure LLM task over
data the harness already holds.

---

## Data Model Changes

### New `ComparisonNarrative` dataclass

```python
@dataclass(frozen=True)
class ComparisonNarrative:
    listing_ids: list[str]           # IDs of listings included, in ranked order
    narrative: str                   # The generated prose comparison
    winner_id: str | None            # ID of the recommended listing, or None if tied
    winner_reasoning: str            # One sentence on why the winner leads
    key_trade_offs: list[str]        # 2-4 bullet-point trade-offs identified
    buyer_priority_alignment: dict[str, str]  # {priority_name: "met"|"partial"|"missed"}
    model_used: str                  # e.g. "claude-haiku-4-5-20251001"
    source: SourceLabel              # Always "estimated" — AI output is advisory
    h2c_comparison_url: str | None   # Populated if narrative was written to H2C
```

### Extended `BuyerProfile` (no changes to existing fields)

The existing `BuyerProfile` fields supply the priority context the LLM needs.
No schema changes are required for Phase 1.

### Optional future field on `Listing`

```python
@dataclass(frozen=True)
class Listing:
    ...
    # New optional field for Phase 3
    h2c_for_ai_data: dict | None = None  # Raw payload from /pc/[suid_code]/for-the-ai
```

---

## New Files to Create

```
src/skills/narrative_comparison.py
```
Core skill. Builds the LLM prompt from buyer profile + ranked listings, calls the
LLM adapter, parses the structured JSON response into a `ComparisonNarrative`.

```
src/models/prompts.py
```
This file already exists (`src/models/prompts.py`). Add the comparison prompt
template `COMPARISON_PROMPT` here alongside existing prompts.

```
tests/skills/test_narrative_comparison.py
```
Unit tests for prompt construction, JSON parsing, and boundary-label injection.

```
tests/skills/snapshots/comparison_narrative_example.json
```
A recorded example `ComparisonNarrative` for snapshot regression testing.

---

## Changes to Existing Files

### `src/skills/comparison.py`
- Rename the current function to `compare_homes_table(listings) -> str` to preserve
  the existing non-LLM output path (used in demo mode and when no LLM is configured).
- Add a new `compare_homes(listings, profile, llm) -> str | ComparisonNarrative`
  that dispatches to `narrative_comparison.generate_narrative` when `llm` is not None,
  or falls back to `compare_homes_table` when `llm` is None.
- The fallback is important: MCP mode with no LLM configured must still work.

### `src/harness/orchestrator.py`
- Update `compare_top(count)` to pass `self.state.buyer_profile` and `self.llm`
  to the new `compare_homes` dispatcher.
- Add `compare_top_narrative(count: int = 3) -> ComparisonNarrative` that explicitly
  requests the structured `ComparisonNarrative` return type.
- Update `create_comparison` to accept an optional `narrative: ComparisonNarrative`
  argument and include it in the H2C payload.

### `src/connectors/homestocompare_connector.py`
- Add `get_for_ai(suid_code: str) -> dict` method to `HomesToCompareConnector`.
  GETs `/pc/{suid_code}/for-the-ai` and returns the raw JSON.
- Extend `create_comparison` payload to include optional `narrative` field:
  ```python
  payload = {
      "listings": [...],
      "source": "house-hunting-agent-harness",
      "narrative": narrative_text,          # str or None
      "narrative_model": model_used,        # str or None
  }
  ```

### `src/ui/mcp_server.py`
- Update existing `compare_homes` tool to accept `brief: str | None` and call
  the narrative path when a brief is provided.
- Add `create_h2c_comparison` tool (see MCP Server Tools section).

### `src/models/prompts.py`
- Add `COMPARISON_PROMPT` template constant (see prompt design below).

---

## Prompt Design

The comparison prompt is the most sensitive piece of this feature. A badly designed
prompt produces generic output ("both homes have pros and cons") that is worse than
the existing bullet list.

```python
COMPARISON_PROMPT = """\
You are helping a UK home buyer decide between {count} properties.
Their priorities:
- Budget: £{max_budget:,}
- Minimum bedrooms: {min_bedrooms}
- Must-haves: {must_haves}
- Nice-to-haves: {nice_to_haves}
- Maximum commute: {max_commute} minutes to {commute_destination}
- Quiet street required: {quiet_street}

Properties (ranked by match score):
{property_list}

Write a comparison in JSON with this exact structure:
{{
  "narrative": "<3 short paragraphs max. Address the buyer's specific priorities.
                Use actual prices and times. Be honest about misses.>",
  "winner_id": "<listing_id or null if genuinely tied>",
  "winner_reasoning": "<one sentence>",
  "key_trade_offs": ["<trade-off 1>", "<trade-off 2>"],
  "buyer_priority_alignment": {{
    "<priority_name>": "met|partial|missed"
  }}
}}

Rules:
- Do not invent features not present in the listing data.
- Do not give legal, mortgage, survey, inspection, or negotiation advice.
- If commute data is missing for a property, say so explicitly.
- Every factual claim must be attributable to the listing data above.
- Mark your output as estimated — AI analysis, not professional advice.
"""
```

---

## MCP Server Tools

### Updated existing tool

```python
@mcp.tool()
def compare_homes(
    listings: list[dict],
    brief: str | None = None,
) -> str | dict:
    """Generate a comparison of up to 5 listings.

    Without a brief: returns a formatted table (no LLM required).
    With a brief: returns a structured ComparisonNarrative as a dict, including
    a narrative paragraph written specifically to the buyer's stated priorities,
    a recommended winner with reasoning, and a list of key trade-offs.

    When a brief is provided, requires the ANTHROPIC_API_KEY or OPENAI_API_KEY
    environment variable to be set.

    Returns either a plain string (table mode) or a dict with keys:
    narrative, winner_id, winner_reasoning, key_trade_offs,
    buyer_priority_alignment.
    """
    ...
```

### New tool

```python
@mcp.tool()
def create_h2c_comparison(
    listings: list[dict],
    brief: str | None = None,
    include_narrative: bool = True,
) -> dict:
    """Push listings to HomesToCompare and get a shareable comparison URL.

    If include_narrative is True and a brief is provided, generates an AI
    narrative and includes it in the H2C payload, so the comparison page at
    the returned URL shows the AI analysis.

    Requires H2C_BASE_URL and H2C_HARNESS_KEY environment variables.

    Returns:
        {
          "status": "ok" | "skipped",
          "comparison_url": "https://homestocompare.com/pc/XXXXX/overview",
          "for_ai_url": "https://homestocompare.com/pc/XXXXX/for-the-ai",
          "narrative_included": true | false,
          "reason": "<only present if status is skipped>"
        }
    """
    ...
```

```python
@mcp.tool()
def fetch_h2c_for_ai(suid_code: str) -> dict:
    """Fetch the machine-readable payload for an H2C comparison page.

    Calls GET /pc/{suid_code}/for-the-ai on HomesToCompare. Returns the
    full structured data including listing attributes, prior AI notes, and
    any enrichment data H2C has stored.

    Useful for enriching a comparison with data the harness does not hold
    locally (EPC rating, price history, listing age, etc.).

    Requires H2C_BASE_URL and H2C_HARNESS_KEY environment variables.
    """
    ...
```

---

## Implementation Phases

### Phase 1 — Narrative comparison (local, no H2C write-back)
**Deliverable:** `compare_homes(listings, profile, llm)` returns a `ComparisonNarrative`.

- Implement `src/skills/narrative_comparison.py` with `generate_narrative()`.
- Build prompt construction using `COMPARISON_PROMPT` template.
- Parse LLM JSON response into `ComparisonNarrative`; on parse failure, fall back
  to table comparison with an error note.
- Update `compare_top` in orchestrator to use narrative path when LLM is set.
- Update MCP `compare_homes` tool to accept `brief` parameter.
- CLI `compare_top` output uses narrative prose when LLM is available.

### Phase 2 — H2C read enrichment
**Deliverable:** Comparison prompt is enriched with data from `/for-the-ai`.

- Implement `HomesToCompareConnector.get_for_ai(suid_code)`.
- In `HouseHuntOrchestrator.create_comparison()`: after creating the H2C comparison,
  fetch the `/for-the-ai` payload and store it in `session_state`.
- Pass the `/for-the-ai` data into the narrative prompt as additional context.
- Add `fetch_h2c_for_ai` MCP tool.

### Phase 3 — H2C narrative write-back
**Deliverable:** Generated narrative appears on the H2C comparison page.

- Extend `create_comparison` H2C payload with `narrative` and `narrative_model`.
- H2C `/api/house-hunt/create-comparison` endpoint (H2C-side work) stores and
  surfaces narrative on `/pc/[suid_code]/overview`.
- Return `for_ai_url` in `create_h2c_comparison` MCP tool response.
- Add integration test: create comparison → fetch `/for-the-ai` → assert narrative
  field is present.

### Phase 4 — Comparison quality feedback loop
**Deliverable:** Buyers can rate narrative quality; ratings improve future prompts.

- Add `rate_comparison(suid_code, rating: 1|2|3|4|5, feedback: str)` MCP tool.
- Store ratings in trace file alongside the narrative.
- Export rating data to CSV as part of Phase 06 export feature.
- (Long-term) Use ratings corpus to fine-tune prompt or select better models.

---

## Testing Plan

### Unit tests

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_narrative_prompt_includes_must_haves` | profile with `must_haves=["garden"]`, 2 listings | prompt string contains "garden" |
| `test_narrative_prompt_includes_prices` | listings with prices 450000, 480000 | prompt contains "£450,000" and "£480,000" |
| `test_parse_llm_response_valid_json` | valid JSON response from LLM | `ComparisonNarrative` with correct fields |
| `test_parse_llm_response_code_block` | JSON wrapped in ` ```json ``` ` | still parses correctly |
| `test_parse_llm_response_malformed` | invalid JSON | falls back to table comparison |
| `test_compare_homes_no_llm` | listings only, no brief | returns plain string (table format) |
| `test_compare_homes_with_llm` | listings + brief + mock LLM | returns `ComparisonNarrative` |
| `test_winner_id_valid` | LLM returns `winner_id` matching a listing | `ComparisonNarrative.winner_id` is that listing's ID |
| `test_winner_id_invalid` | LLM returns unknown `winner_id` | harness sets `winner_id=None` with warning |
| `test_source_label_always_estimated` | any narrative | `source == "estimated"` |

### Snapshot test

```python
def test_narrative_snapshot():
    """Regression: narrative output for the standard demo brief must not change
    unless intentionally updated."""
    profile = BuyerProfile(
        location_query="King's Cross",
        max_budget=700_000,
        min_bedrooms=3,
        max_commute_minutes=45,
        must_haves=["garden", "quiet"],
        nice_to_haves=["period"],
    )
    listings = load_demo_listings()[:3]
    mock_llm = FixtureLlm("snapshots/comparison_narrative_example.json")
    narrative = generate_narrative(listings, profile, mock_llm)
    assert narrative.winner_id is not None
    assert len(narrative.key_trade_offs) >= 2
    assert "garden" in narrative.narrative.lower()
```

### Integration test (requires live LLM)

```bash
export ANTHROPIC_API_KEY=<key>
uv run pytest tests/skills/test_narrative_comparison.py -m integration -v
# Expected: narrative text >200 chars, winner_id is one of the listing IDs,
#           at least one key_trade_off references a must-have priority
```

---

## Open Questions

1. **JSON reliability.** Claude Haiku sometimes wraps JSON in markdown fences and
   sometimes returns prose with JSON embedded. The existing `_extract_json` in
   `src/skills/intake.py` handles the fence case. Is the same extractor robust enough
   for the comparison response, or does the comparison prompt need a stricter system
   prompt instruction?

2. **Winner declaration sensitivity.** Telling a buyer "Listing B is the winner"
   could feel presumptuous. Should `winner_id` be optional and gated behind a buyer
   preference ("show me a recommendation" vs "just compare"), or should we always
   include it but frame it softly in the narrative?

3. **Comparison count.** The existing `compare_top(count=3)` caps at 3. The bullet
   table can handle 5 comfortably. LLM comparisons of 4–5 homes get expensive and
   verbose. Should the narrative path be capped at 3 listings, with the table fallback
   used for 4–5?

4. **H2C narrative storage.** If the harness writes a narrative to H2C and the buyer
   then runs the harness again (with different listings), the old narrative is
   overwritten. Should H2C version narratives, or should each `create_comparison`
   call always create a new comparison (new `suid_code`)?

5. **Buyer_priority_alignment field.** The proposed schema maps each priority name to
   "met|partial|missed". But the LLM has to assign these labels, and "partial" is
   ambiguous (is a garden that's described as "small rear patio" partial or missed?).
   Should the harness compute these labels deterministically from `RankedListing.matched`
   and `missed`, and only use the LLM for narrative prose?

6. **Model selection.** Should the comparison use Haiku (cheap, fast, occasionally
   shallow) or Sonnet (more expensive, better reasoning)? Should the buyer be able
   to choose via CLI flag `--comparison-model`?
