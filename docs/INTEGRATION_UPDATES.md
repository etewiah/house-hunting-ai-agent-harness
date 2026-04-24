# Agent Harness — Updates Required for HomesToCompare Integration

> Historical note: this document predates the verified public H2C publishing flow.
> Browser-assisted comparison publishing now uses the public `/api/create-comparison`
> path through `HomesToComparePublicConnector`, with verified photo validation in the
> harness. Do not use the older `H2C_SERVICE_KEY` guidance here for current
> browser-assisted H2C publishing work.

**Scope:** Changes inside `house-hunting-ai-agent-harness/` needed to support deep integration with the HomesToCompare TypeScript application, maintain the harness as a useful standalone reference, and evolve it toward v0.2.

## Status note

This document started as a forward-looking integration checklist. Some items here are now
implemented in the harness, while others remain roadmap or coordination items with the main
HomesToCompare application.

### Implemented in this repo now
- provider-backed HomesToCompare listing support
- HomesToCompare comparison creation from the orchestrator
- optional LLM-backed intake
- fair-housing-sensitive generated-language checks
- missing-commute warning coverage
- README integration guidance

### Still mainly roadmap / coordination items
- any new HomesToCompare API endpoints required outside this repo
- deeper live integration verification against the main TypeScript app
- any broader v0.2 expansion not yet reflected in the current codebase

---

## 1. HomesToCompare HTTP connector — wire up to HomesToCompare API

**Current state:** `src/connectors/mcp_client.py` is a real MCP stub and should remain reserved for MCP protocol work.

**Required change:** Implement a separate direct HTTP connector that calls the HomesToCompare comparison creation API, enabling the harness to create comparisons from Python without browser automation. Do not call this an MCP connector unless it implements the MCP protocol.

### `src/connectors/homestocompare_connector.py` *(new)*

```python
from __future__ import annotations

import json
import urllib.request
from src.models.schemas import BuyerProfile, Listing


class HomesToCompareConnector:
    """
    Thin HTTP connector to the HomesToCompare API.
    Enables the harness to create comparisons from ranked listings.
    """

    BASE_URL = "https://homestocompare.com"

    def __init__(self, service_key: str) -> None:
        self.service_key = service_key

    def create_comparison(self, left_url: str, right_url: str) -> dict[str, object]:
        """
        POST /api/house-hunt/create-comparison
        Returns { success, comparison_id, comparison_url } or raises on error.
        """
        payload = json.dumps({
            "left_url": left_url,
            "right_url": right_url,
        }).encode()

        req = urllib.request.Request(
            f"{self.BASE_URL}/api/house-hunt/create-comparison",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-house-hunt-key": self.service_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())

    def create_comparison_from_listings(
        self, listing_a: Listing, listing_b: Listing
    ) -> dict[str, object]:
        if not listing_a.source_url or not listing_b.source_url:
            raise ValueError("Both listings must have source_url to create a comparison.")
        return self.create_comparison(listing_a.source_url, listing_b.source_url)
```

**Update `src/connectors/__init__.py`:** Export `HomesToCompareConnector`.

**Update `.env.example`:**
```
# HomesToCompare integration
H2C_SERVICE_KEY=your-house-hunt-service-key-here
H2C_BASE_URL=https://homestocompare.com
```

---

## 2. Real listing connector — Supabase/HTTP

**Current state:** listing search is provider-backed. `H2CListingConnector` fetches HomesToCompare listings, and `LocalCsvListingConnector` reads explicit CSV exports.

**Required change:** Keep listing search provider-backed; do not add built-in fixture fallbacks.

### `src/connectors/h2c_listing_connector.py` *(new)*

```python
from __future__ import annotations

import json
import urllib.request
import urllib.parse
from src.models.schemas import BuyerProfile, Listing
from src.skills.listing_search import filter_listings


class H2CListingConnector:
    """
    Fetches listings from the HomesToCompare REST API.
    Requires an H2C_READ_KEY or equivalent dedicated read-only service key. Do not reuse the management password for this connector.
    """

    def __init__(self, base_url: str, read_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.read_key = read_key

    def search(self, profile: BuyerProfile, limit: int = 200) -> list[Listing]:
        params = urllib.parse.urlencode({
            "location": profile.location_query,
            "max_budget": profile.max_budget,  # whole currency units
            "min_bedrooms": max(1, profile.min_bedrooms - 1),
            "limit": limit,
        })
        req = urllib.request.Request(
            f"{self.base_url}/api/listings/search?{params}",
            headers={"x-h2c-read-key": self.read_key},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            rows = json.loads(resp.read())

        listings = [_row_to_listing(row) for row in rows]
        return filter_listings(profile, listings)


def _row_to_listing(row: dict[str, object]) -> Listing:
    """Map a HomesToCompare DB listing row to a harness Listing."""
    price_cents = row.get("price_sale_current") or 0
    return Listing(
        id=str(row["id"]),
        title=str(row.get("title") or row.get("ai_suggested_title") or "Untitled"),
        price=round(int(price_cents) / 100),           # cents → whole units
        bedrooms=int(row.get("count_bedrooms") or 0),
        bathrooms=int(row.get("count_bathrooms") or 0),
        location=str(row.get("market") or ""),
        commute_minutes=None,                           # not in DB yet
        features=list(row.get("sale_listing_features") or []),
        description=str(row.get("description") or row.get("description_short") or ""),
        source_url=str(row.get("listing_url") or row.get("import_url") or ""),
    )
```

**Note:** The `/api/listings/search` endpoint does not yet exist in the main app — it needs to be added (see the H2C implementation plan). The endpoint should return a minimal listing DTO or carefully redacted row shape, not an unrestricted admin dump. This connector is built in parallel with that endpoint.

---

## 3. Orchestrator — expose `create_comparison` step

**Current state:** `HouseHuntOrchestrator.prep_next_steps()` prepares affordability, tour questions, and offer brief but does not create a HomesToCompare comparison.

**Required change:** Add a `create_comparison(count: int = 2)` method that takes the top-ranked listings, creates a comparison via the `HomesToCompareConnector`, and returns the URL.

### Changes to `src/harness/orchestrator.py`

Add import:
```python
from src.connectors.homestocompare_connector import HomesToCompareConnector
```

Add parameter to `__init__`:
```python
def __init__(
    self,
    listings: ListingProvider,
    trace_dir: str = ".traces",
    h2c_connector: HomesToCompareConnector | None = None,
) -> None:
    ...
    self.h2c = h2c_connector
```

Add method:
```python
def create_comparison(self, count: int = 2) -> dict[str, object]:
    """
    Creates a HomesToCompare comparison for the top `count` ranked listings.
    Requires h2c_connector to be set and listings to have source_url.
    Returns the comparison URL or a reason why it could not be created.
    """
    if self.h2c is None:
        return {"status": "skipped", "reason": "No HomesToCompare connector configured."}
    if len(self.state.ranked_listings) < 2:
        return {"status": "skipped", "reason": "Need at least 2 ranked listings to compare."}

    top = [item.listing for item in self.state.ranked_listings[:count]]
    if not top[0].source_url or not top[1].source_url:
        return {"status": "skipped", "reason": "Top listings lack source_url."}

    result = self.h2c.create_comparison(top[0].source_url, top[1].source_url)
    self.tracer.record("comparison.created", result)
    return result
```

---

## 4. Intake — replace regex with LLM-powered extraction (optional v0.2 upgrade)

**Current state:** `parse_buyer_brief()` uses regex heuristics. It fails on non-standard phrasing and has a hardcoded location list containing only "King's Cross."

**Recommended change:** Add an optional `llm_adapter` parameter. When provided, use it for extraction. When absent, fall back to the existing regex.

### Changes to `src/skills/intake.py`

```python
from __future__ import annotations

import json
import os
import re
from typing import Protocol
from src.models.schemas import BuyerProfile


class LlmAdapter(Protocol):
    def generate(self, prompt: str, model: str) -> str: ...


_INTAKE_PROMPT = """
You are a structured data extractor. Parse the buyer brief into JSON only.
Brief: "{brief}"
Return: {{"location_query":str,"max_budget":int,"min_bedrooms":int,"max_commute_minutes":int|null,"must_haves":list[str],"nice_to_haves":list[str],"quiet_street_required":bool}}
"""


def parse_buyer_brief(text: str, llm: LlmAdapter | None = None) -> BuyerProfile:
    if llm is not None:
        return _parse_with_llm(text, llm)
    return _parse_with_regex(text)


def _parse_with_llm(text: str, llm: LlmAdapter) -> BuyerProfile:
    raw = llm.generate(_INTAKE_PROMPT.format(brief=text), model=os.getenv("BUYER_AGENT_INTAKE_MODEL", "claude-haiku-4-5"))
    parsed = json.loads(raw.strip())
    return BuyerProfile(
        location_query=parsed.get("location_query", "unknown"),
        max_budget=parsed.get("max_budget", 0),
        min_bedrooms=parsed.get("min_bedrooms", 3),
        max_commute_minutes=parsed.get("max_commute_minutes"),
        must_haves=parsed.get("must_haves", []),
        nice_to_haves=parsed.get("nice_to_haves", []),
        quiet_street_required=parsed.get("quiet_street_required", False),
    )


def _parse_with_regex(text: str) -> BuyerProfile:
    """Original regex implementation — used when no LLM is available."""
    lowered = text.lower()
    # ... (existing regex logic unchanged)
```

---

## 5. Models — missing commute coverage

**Current state:** `commute_minutes` is `None` for most real listings. This means the `warnings` array in `RankedListing` can contain `"commute time missing"` in production.

**Recommended change:** Keep inline test listings with `commute_minutes=None` to ensure the warning path is covered without bundled listing fixtures.

**Add test to `evals/tests/test_ranking.py`:**
```python
def test_missing_commute_generates_warning():
    profile = BuyerProfile(
        location_query="test", max_budget=600000, min_bedrooms=2,
        max_commute_minutes=45, must_haves=[], nice_to_haves=[],
        quiet_street_required=False,
    )
    listing = Listing(
        id="L005", title="No Commute Data", price=550000,
        bedrooms=2, bathrooms=1, location="Hackney",
        commute_minutes=None, features=["walkable"],
        description="", source_url="",
    )
    result = rank_listing(profile, listing)
    assert "commute time missing" in result.warnings
```

---

## 6. Policies — add fair-housing-sensitive generated-language checks

**Current state:** `PROHIBITED_CLAIMS` covers legal, mortgage, survey, inspection, fiduciary advice. Fair-housing-sensitive language is mentioned in `docs/guardrails.md` but not implemented in `policies.py`.

**Required change:** Do not reject buyer intake just because a user says they care about schools or family needs. Instead, add a separate generated-language check used on assistant recommendations so the harness does not steer using demographic proxies.

### Changes to `src/harness/policies.py`

```python
PROHIBITED_CLAIMS = [
    "legal advice",
    "mortgage advice",
    "survey advice",
    "inspection advice",
    "fiduciary advice",
]

FAIR_HOUSING_SENSITIVE_RECOMMENDATION_PHRASES = [
    "good schools nearby",
    "safe neighbourhood",
    "safe neighborhood",
    "family-friendly area",
]
```

**Add test to `evals/tests/test_guardrails.py`:**
```python
def test_fair_housing_terms_detected_in_generated_recommendations():
    violations = check_generated_recommendation_language("This is a safe neighbourhood with good schools nearby.")
    assert len(violations) > 0
```

**Note:** These additions should not affect buyer intake. The HomesToCompare TypeScript implementation should mirror the distinction between prohibited advice claims and fair-housing-sensitive generated recommendation language.

---

## 7. Tracing — structured event names and JSON schema

**Current state:** `TraceRecorder.record(name, payload)` is free-form. Event names like `"intake.profile_created"` are strings with no enforcement.

**Recommended change:** Define an `EventName` literal type and a minimal JSON schema for trace files. This enables the HomesToCompare app to consume harness traces if they are ever exported.

### Changes to `src/harness/tracing.py`

```python
from typing import Literal

EventName = Literal[
    "intake.profile_created",
    "triage.ranked_listings",
    "triage.explanations",
    "comparison.summary",
    "comparison.created",
    "next_steps.prepared",
]
```

Update `record` signature:
```python
def record(self, name: EventName, payload: object) -> None:
```

This is a type annotation only — no runtime change, but it enables mypy checking and documents the contract.

---

## 8. README — add integration section

Add a section to `README.md` explaining how to connect the harness to a live HomesToCompare instance.

```markdown
## HomesToCompare Integration

The harness ships with a connector for the [HomesToCompare](https://homestocompare.com) comparison platform.

To use it:
1. Set `H2C_SERVICE_KEY` in your `.env` (see `.env.example`)
2. Pass `HomesToCompareConnector` to `HouseHuntOrchestrator`

```python
from src.connectors.homestocompare_connector import HomesToCompareConnector
from src.harness.orchestrator import HouseHuntOrchestrator
from src.connectors.homestocompare_connector import H2CListingConnector

connector = HomesToCompareConnector(service_key=os.environ["H2C_SERVICE_KEY"])
orchestrator = HouseHuntOrchestrator(
    listings=H2CListingConnector(
        base_url=os.environ["H2C_BASE_URL"],
        read_key=os.environ["H2C_READ_KEY"],
    ),
    h2c_connector=connector,
)
orchestrator.intake("3-bed near schools, budget £650k, 45 min to London")
orchestrator.triage()
result = orchestrator.create_comparison()
print(result["comparison_url"])
```

The harness will rank listings, select the top two with source URLs, and create a
side-by-side comparison at `homestocompare.com/pc/{id}/overview`.
```

---

## 9. CLI search — extend to show comparison URL

**Current state:** `src/ui/cli.py` runs the interactive search workflow but does not call `create_comparison`.

**Required change:** Optionally call `create_comparison` at the end of a search if `H2C_SERVICE_KEY` is set.

### Changes to `src/ui/cli.py`

```python
import os
from src.connectors.homestocompare_connector import HomesToCompareConnector

def main() -> None:
    # ... existing setup ...
    
    h2c_key = os.environ.get("H2C_SERVICE_KEY")
    connector = HomesToCompareConnector(h2c_key) if h2c_key else None
    
    orchestrator = HouseHuntOrchestrator(
        listings=listing_provider,
        trace_dir=cfg.trace_output_dir,
        h2c_connector=connector,
    )
    
    # ... existing intake, triage, explain, compare, next_steps calls ...
    
    if connector:
        print("\n--- Creating HomesToCompare comparison ---")
        result = orchestrator.create_comparison()
        if result.get("success"):
            print(f"Comparison URL: {result['comparison_url']}")
        else:
            print(f"Could not create comparison: {result.get('reason', result)}")
```

---

## 10. New `/api/listings/search` endpoint (needed by `H2CListingConnector`)

This endpoint lives in the HomesToCompare app but is listed here because the harness connector depends on it.

See `docs/improvements/AGENT_HARNESS_INTEGRATION_H2C.md` for full spec. Short form:

```
GET /api/listings/search?location=xxx&max_budget=xxx&min_bedrooms=xxx&limit=200
Auth: dedicated read-only service key
Response: minimal listing DTO[] or explicitly redacted DbListingRow subset
```

The harness `H2CListingConnector._row_to_listing()` is written against this response shape. If the response shape changes, both must be updated together.

---

## Summary of changes

| File | Change type | Phase |
|------|-------------|-------|
| `src/connectors/homestocompare_connector.py` | new | Parallel with H2C Phase 1 |
| `src/connectors/h2c_listing_connector.py` | new | Parallel with H2C Phase 1 |
| `src/harness/orchestrator.py` | modified — add `h2c_connector` param + `create_comparison()` method | Parallel with H2C Phase 1 |
| `src/skills/intake.py` | modified — add optional `llm` adapter parameter | v0.2 |
| `src/harness/policies.py` | modified — add fair housing terms | v0.2 |
| `src/harness/tracing.py` | modified — add `EventName` literal type | v0.2 |
| `evals/tests/test_ranking.py` | modified — add null commute test | immediately |
| `evals/tests/test_guardrails.py` | modified — add fair housing test | v0.2 |
| `.env.example` | modified — add H2C vars | immediately |
| `README.md` | modified — add integration section | immediately |
| `src/ui/cli.py` | modified — call create_comparison if key set | Parallel with H2C Phase 1 |
| `docs/INTEGRATION_UPDATES.md` | new — this file | immediately |
