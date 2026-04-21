# 02 - Richer AI-Powered Comparison

## Purpose

The harness should help a buyer understand trade-offs between properties, not just print
facts side by side. The comparison capability should work with any listing source and any
geography. It should use the buyer's stated priorities, available listing data, and any
optional enrichments to produce a concise, evidence-grounded comparison.

The output is advisory. It should help the buyer focus their next questions; it must not
pretend to be mortgage, legal, survey, valuation, or local-authority advice.

## Harness Contract

The comparison capability should accept:

- Buyer profile or raw brief.
- Two or more listings, preferably already ranked.
- Optional enrichment data: commute, area intelligence, affordability, image observations,
  notes, viewing questions, or platform-specific metadata.
- Optional style constraints: concise, detailed, partner-friendly, broker-friendly, etc.

It should return:

- A short narrative comparison.
- Key trade-offs.
- Priority alignment for each listing.
- A recommended leading option only when the evidence supports one.
- Missing-data warnings.
- Model/provider provenance.

## LLM Responsibilities

The LLM should:

- Ground every factual claim in supplied listing or enrichment data.
- Compare against the buyer's priorities, not generic property preferences.
- Highlight important unknowns instead of filling gaps.
- Quantify trade-offs where data supports it.
- Avoid overconfident language when data is incomplete.
- Keep professional advice boundaries explicit.

The LLM may infer what matters from the brief, but it should not invent property features,
local risks, fees, legal status, school catchments, or commute times.

## Suggested Data Shape

```python
@dataclass(frozen=True)
class ComparisonNarrative:
    listing_ids: list[str]
    narrative: str
    key_trade_offs: list[str]
    priority_alignment: dict[str, dict[str, str]]
    winner_id: str | None
    winner_reasoning: str | None
    model_used: str
    source: SourceLabel = "estimated"
    warnings: list[str] = field(default_factory=list)
```

`priority_alignment` can be shaped as `{listing_id: {priority: "met|partial|missed|unknown"}}`.
Where possible, deterministic ranking data should compute these labels, with the LLM
responsible for prose and synthesis.

## Prompt Principles

The prompt should be compact and portable:

- State the buyer's priorities.
- Provide normalized listing facts.
- Provide optional enrichment summaries with source labels.
- Require structured output.
- Require missing-data disclosure.
- Prohibit professional advice and unsupported claims.

Avoid prompts that assume a specific country, property portal, or dataset.

## Platform Integration

If a hosting platform such as HomesToCompare is available, the comparison can be read from
or written back to that platform. The core harness should treat this as an adapter:

- Read extra machine-readable comparison data if the platform provides it.
- Write the generated narrative back if the platform supports persistence.
- Return platform URLs as optional metadata.

The comparison skill should still work without any platform connector.

## Implementation Guidance

- Keep the existing non-LLM table comparison as a fallback.
- Use the repository's `LlmAdapter` pattern rather than tying the feature to one model
  vendor.
- Parse structured model output defensively.
- Validate `winner_id` against supplied listing IDs.
- Include warnings when the model response is malformed or incomplete.

## Testing Focus

- Prompt includes buyer priorities and listing facts.
- Missing commute or enrichment data is disclosed.
- Invalid JSON falls back gracefully.
- Invalid winner IDs are removed or warned.
- The non-LLM fallback still works.
- Generated comparisons do not include unsupported professional advice.

## Open Questions

- Should the harness always include a recommended winner, or make that opt-in?
- Should narrative comparisons be capped at three listings for readability?
- Which priority-alignment labels should be computed deterministically rather than by LLM?
