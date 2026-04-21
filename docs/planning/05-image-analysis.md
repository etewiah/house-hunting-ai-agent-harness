# 05 — Listing Image Analysis

## Goal

Property photos are the first thing most buyers look at, yet the harness ignores them
entirely. An AI-powered image analysis pass gives the buyer a pre-viewing flag on
things a photograph can reveal: a kitchen that was last updated in 1994, signs of damp
on a ceiling, a garden that is actually a 2m² concrete yard, or a "study" that is
clearly a bedroom cupboard with a window.

The goal is not to replace a professional survey or a physical viewing. It is to help
the buyer triage. A listing that scores 92/100 on price, bedrooms, and commute but
shows a damp corner in the main bedroom photo should carry a warning before the buyer
books a viewing. Conversely, a listing with period features and excellent natural light
in the photos should have those attributes surfaced, because agent descriptions are
often vague.

Key constraints:

- All image analysis results are labelled `source: "estimated"` and marked as advisory
- The output must not state facts, only observations ("appears to show", "may indicate")
- Image analysis is an optional enrichment step — the harness must work without it
- Claude Haiku handles images cheaply; the batch approach (multiple images per API
  call) keeps costs low
- H2C listing image URLs are the primary source; the connector must be extended to
  read them

---

## HomesToCompare Integration

H2C listings have associated images. The `_row_to_listing` mapper in
`src/connectors/homestocompare_connector.py` currently ignores image-related fields
entirely.

**Integration points:**

1. **Image URL extraction.** H2C listing rows likely contain a `images` array or
   `primary_image_url` field. The mapper should read these into the new
   `Listing.image_urls` field.

2. **Image analysis storage.** After the harness runs image analysis, the
   `ImageAnalysis` result can be written back to H2C via
   `/api/house-hunt/enrich-listing`. The H2C comparison page could then surface
   "AI image notes" on the `/pc/[suid_code]/details` or `/pc/[suid_code]/for-the-ai`
   page, clearly marked as estimated.

3. **For-AI endpoint enrichment.** The `/for-the-ai` endpoint on a comparison page
   should include any stored `ImageAnalysis` data so the harness can read back its own
   prior analysis without re-calling the vision model.

4. **Displaying in comparison.** When the buyer calls `compare_homes` (Feature 02),
   the narrative prompt can include image analysis observations as additional context:
   "Note: image analysis flagged possible damp in listing B's kitchen."

---

## External APIs / Services

### Anthropic Messages API — Claude Vision
- Models: `claude-haiku-4-5-20251001` (cheapest per image), `claude-sonnet-4-6`
  (better at detail recognition)
- Cost (Haiku): ~$0.25 per 1M input tokens. An image at 1080px costs approximately
  1,600–2,400 tokens. At 6 images per listing × $0.25/M: roughly $0.004 per listing.
  For 10 listings: ~$0.04. Very affordable.
- Cost (Sonnet): ~12× more expensive per token. Use selectively for highest-priority
  listings only.
- Image input: base64-encoded or URL-referenced via `{"type": "image_url", "url": ...}`
  in the messages API.
- Batch limit: Up to 20 images per API call. For 6 images per listing, one call
  suffices.
- Rate limits: 5 images/second on Haiku tier 1. Batch all listing images in a single
  call to avoid hitting this.
- URL: https://docs.anthropic.com/en/api/messages

### OpenAI Vision (GPT-4o)
- Already supported via `openai_adapter.py`; GPT-4o accepts images in the same
  messages API format.
- Cost: GPT-4o-mini with vision: ~$0.15/1M tokens. Similar cost tier to Haiku.
- Suitable as a drop-in alternative when `OPENAI_API_KEY` is set.

### Image download / HTTP fetch
- No third-party service needed. Python `urllib.request` (already used in the
  connector) fetches image bytes for base64 encoding.
- H2C image URLs should be directly accessible; no auth header needed for CDN images.

---

## Data Model Changes

### Extended `Listing` dataclass

```python
@dataclass(frozen=True)
class Listing:
    id: str
    title: str
    price: int
    bedrooms: int
    bathrooms: int
    location: str
    commute_minutes: int | None
    features: list[str]
    description: str
    source_url: str
    # Existing additions from Feature 01
    address: str | None = None
    postcode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    commute_mode: str | None = None
    commute_source: SourceLabel = "missing"
    # New in Feature 05
    image_urls: list[str] = field(default_factory=list)
    image_analysis: ImageAnalysis | None = None
```

### New `ImageFlag` dataclass

```python
@dataclass(frozen=True)
class ImageFlag:
    category: str       # "condition" | "layout" | "positive" | "uncertainty"
    label: str          # e.g. "possible damp", "good natural light", "dated kitchen"
    confidence: str     # "low" | "medium" | "high"
    image_index: int    # 0-based index into Listing.image_urls
    note: str           # One sentence describing what was observed
    source: SourceLabel # Always "estimated" — never "listing_provided"
```

### New `ImageAnalysis` dataclass

```python
@dataclass(frozen=True)
class ImageAnalysis:
    listing_id: str
    image_urls_analysed: list[str]      # Subset of image_urls that were sent to model
    flags: list[ImageFlag]              # All flags raised, sorted by category
    summary: str                        # 1–2 sentence prose summary
    positive_highlights: list[str]      # Feature strings to add to Listing.features
    condition_warnings: list[str]       # Strings to add to RankedListing.warnings
    model_used: str                     # e.g. "claude-haiku-4-5-20251001"
    source: SourceLabel                 # Always "estimated"
    analysis_date: str                  # ISO 8601 date string
    images_skipped: int                 # Count of images not sent (e.g. floor plans)
    error: str | None                   # Set if analysis failed; listing still usable
```

### `SourceLabel` extension

The existing `SourceLabel` literal already includes `"estimated"`. No change needed.
All `ImageAnalysis` and `ImageFlag` objects use `source="estimated"` without exception.

---

## New Files to Create

```
src/skills/image_analysis.py
```
Core skill. Fetches image bytes, assembles multi-image prompt, calls the LLM adapter,
parses the structured JSON response into `ImageAnalysis`. Handles partial failures
(some images 404, some too large) gracefully.

```
src/connectors/image_fetcher.py
```
Downloads images from URLs, returns base64-encoded bytes with MIME type. Respects
max size limits (skip images >3MB). Detects and skips floor plan images (using URL
heuristics: "floorplan", "floor_plan", "fp_" in URL).

```
tests/skills/test_image_analysis.py
```
Unit tests for prompt construction, JSON parsing, confidence normalisation, and
partial failure handling.

```
tests/connectors/test_image_fetcher.py
```
Tests for image download, size checking, and floor plan detection.

```
tests/skills/fixtures/image_analysis_response.json
```
Recorded LLM response fixture for snapshot testing.

---

## Changes to Existing Files

### `src/models/schemas.py`
- Add `ImageFlag` and `ImageAnalysis` dataclasses.
- Add `image_urls: list[str]` and `image_analysis: ImageAnalysis | None` to
  `Listing`. Both have defaults so existing code continues to work without changes.

### `src/connectors/homestocompare_connector.py`
- Update `_row_to_listing` to read `images`, `image_urls`, `photos`, or
  `primary_image_url` from the H2C row. Normalise to a `list[str]` of full URLs.
- Add `enrich_listing_images(listing_id: str, analysis: ImageAnalysis) -> dict`
  to `HomesToCompareConnector`.

### `src/harness/orchestrator.py`
- Add `analyse_images(listing_ids: list[str] | None = None, max_images: int = 6)`
  method.
  - If `listing_ids` is None, analyses all shortlisted or top-5 ranked listings.
  - For each listing, calls `image_analysis.analyse_listing(listing, llm)`.
  - Stores result in `self.state` and replaces the `Listing` with an enriched copy
    (via `dataclasses.replace`) that has `image_analysis` populated.
  - Appends `condition_warnings` to the corresponding `RankedListing.warnings`.
- The method is guarded: if `self.llm` is None, logs a warning and returns without
  error.

### `src/harness/session_state.py`
- Add `image_analyses: dict[str, ImageAnalysis]` field (keyed by listing_id).

### `src/skills/ranking.py`
- After image analysis is available, `rank_listing` should incorporate
  `condition_warnings` from `ImageAnalysis` as additional `warnings`. These do not
  affect the numerical score (to avoid penalising based on advisory AI output) but
  are surfaced visibly to the buyer.
- Add a helper `apply_image_analysis(ranked: RankedListing, analysis: ImageAnalysis) -> RankedListing`
  that returns a new `RankedListing` with the analysis warnings merged in.

### `src/ui/cli.py`
- After comparison output, add an "Image Analysis" section if any listings have
  `image_analysis` populated.
- Display: listing title, summary sentence, any condition warnings, and positive
  highlights.
- Prominently label: "Image analysis is estimated AI output and not a professional
  survey."

### `src/connectors/mock_listing_api.py`
- Add `image_urls` to at least 2 mock listings using publicly accessible placeholder
  images (e.g. Unsplash or Wikimedia Commons URLs) so the integration test can run
  without real listing data.

---

## MCP Server Tools

```python
@mcp.tool()
def analyse_listing_images(
    listing: dict,
    max_images: int = 6,
    model: str | None = None,
) -> dict:
    """Analyse property photos for a single listing using Claude Vision.

    Fetches up to max_images from listing.image_urls, sends them to the
    vision model in a single API call, and returns structured observations.

    Floor plan images are automatically detected and excluded (using URL
    heuristics). Images larger than 3MB are skipped.

    Args:
        listing: A listing dict with image_urls (list of URL strings).
        max_images: Maximum number of images to analyse (default 6).
        model: Override the default vision model. Defaults to
               BUYER_AGENT_VISION_MODEL env var or claude-haiku-4-5-20251001.

    Returns an image_analysis dict with:
        flags: List of {category, label, confidence, image_index, note}
        summary: 1-2 sentence overall assessment
        positive_highlights: Features worth noting (period details, light, etc.)
        condition_warnings: Issues to investigate at viewing
        model_used: The model that produced this analysis
        source: Always "estimated"
        images_skipped: Number of images not sent

    IMPORTANT: All output is estimated AI analysis, not a professional survey
    or structural inspection. Never rely on this output alone.

    Requires ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable.
    """
    ...
```

```python
@mcp.tool()
def analyse_listings_images_batch(
    listings: list[dict],
    max_images_per_listing: int = 6,
) -> list[dict]:
    """Analyse property photos for multiple listings.

    Runs image analysis for each listing sequentially (not concurrently, to
    respect API rate limits). Returns the listings with image_analysis added
    to each dict.

    Listings without image_urls are returned unchanged.
    Listings where analysis fails have image_analysis.error set.

    Suitable for running after rank_listings to enrich the top results.
    """
    ...
```

---

## Prompt Design

The vision prompt is the most consequential part of this feature. An over-eager prompt
produces spurious warnings that undermine buyer trust. An under-specified prompt
produces generic output.

```python
IMAGE_ANALYSIS_PROMPT = """\
You are reviewing property listing photos for a UK home buyer.
Analyse the provided images and return JSON with this exact structure:

{
  "flags": [
    {
      "category": "condition|layout|positive|uncertainty",
      "label": "<short label, e.g. 'possible damp', 'good natural light'>",
      "confidence": "low|medium|high",
      "image_index": <0-based int>,
      "note": "<one sentence describing what you see>"
    }
  ],
  "summary": "<1-2 sentences overall>",
  "positive_highlights": ["<feature 1>", ...],
  "condition_warnings": ["<warning 1>", ...]
}

Category guidance:
- "condition": physical condition issues visible in photos (damp, dated fittings,
  cracked surfaces, mould, peeling paint, blocked gutters visible from exterior shots)
- "layout": layout or space observations (dark rooms, awkward flow, small rooms,
  low ceilings, good open-plan layout, room proportions)
- "positive": genuinely positive features visible (period cornicing, sash windows,
  well-maintained garden, good natural light, high ceilings, modern kitchen)
- "uncertainty": images that are too dark, blurry, or limited to draw conclusions

Rules:
- Only describe what is visible. Never invent features.
- Use hedging language: "appears to show", "may indicate", "visible in image X".
- Confidence "high" means clearly visible. "low" means a possibility only.
- Do not comment on decor preferences (paint colours, furniture style).
- Do not make structural or legal assessments.
- If an image appears to be a floor plan, note it in uncertainty flags only.
- Maximum 8 flags total.
- All output is estimated AI analysis, advisory only.
"""
```

---

## Implementation Phases

### Phase 1 — Image URL extraction from H2C
**Deliverable:** `Listing.image_urls` is populated for H2C listings.

- Update `_row_to_listing` to read image fields.
- Add `image_urls: list[str]` to `Listing` schema.
- Add `image_urls` to `_to_listing` in `mcp_server.py`.
- Mock listings gain `image_urls` with placeholder URLs.
- No vision API calls yet.

### Phase 2 — Single-listing image analysis
**Deliverable:** `analyse_listing_images` MCP tool works end-to-end.

- Implement `src/connectors/image_fetcher.py`.
- Implement `src/skills/image_analysis.py`:
  - `fetch_images(urls, max_images, max_bytes_each)` using image fetcher
  - `build_vision_prompt(images)` returning `list[dict]` for messages API
  - `analyse_listing(listing, llm, max_images) -> ImageAnalysis`
  - `parse_analysis_response(raw_json, listing, urls) -> ImageAnalysis`
- `analyse_listing_images` MCP tool implemented.
- Unit tests with fixture response JSON.

### Phase 3 — Orchestrator integration and CLI display
**Deliverable:** `house-hunt search` shows image analysis for top listings.

- `HouseHuntOrchestrator.analyse_images()` implemented.
- CLI displays image analysis section.
- `RankedListing.warnings` includes image condition warnings.
- `BUYER_AGENT_VISION_MODEL` env var controls model selection.
- Integration test with real H2C listing images (requires live credentials).

### Phase 4 — H2C write-back and comparison narrative enrichment
**Deliverable:** Image analysis stored on H2C; narrative comparison reads image flags.

- `HomesToCompareConnector.enrich_listing_images()` implemented.
- `analyse_listings_images_batch` MCP tool implemented.
- Comparison narrative prompt (Feature 02) enriched with image observations.
- `/for-the-ai` endpoint read includes stored `image_analysis` data.

---

## Testing Plan

### Unit tests

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_floor_plan_url_detection` | URL containing "floorplan" | image skipped, `images_skipped == 1` |
| `test_image_too_large_skipped` | 4MB image | skipped, `images_skipped == 1` |
| `test_parse_valid_response` | valid JSON fixture | `ImageAnalysis` with correct fields |
| `test_parse_malformed_response` | invalid JSON | `ImageAnalysis.error` set, no exception raised |
| `test_source_always_estimated` | any analysis | all flags have `source == "estimated"`, `ImageAnalysis.source == "estimated"` |
| `test_condition_warning_propagation` | `ImageAnalysis` with condition flag | `RankedListing.warnings` includes that flag's label |
| `test_positive_highlights_not_in_warnings` | positive flag only | `condition_warnings` empty, `positive_highlights` non-empty |
| `test_no_images_returns_graceful` | `Listing.image_urls == []` | `ImageAnalysis.error` set to "no images available" |
| `test_confidence_normalisation` | LLM returns "High" (capitalised) | normalised to "high" |
| `test_max_images_respected` | 10 URLs, `max_images=6` | exactly 6 images fetched, `images_skipped == 4` |

### Snapshot test

```python
def test_image_analysis_snapshot():
    """Regression: fixture response must parse to expected ImageAnalysis."""
    raw = load_fixture("image_analysis_response.json")
    mock_llm = FixtureLlm(raw)
    listing = Listing(id="L1", ..., image_urls=["https://example.com/img1.jpg"])
    analysis = analyse_listing(listing, llm=mock_llm)
    assert analysis.source == "estimated"
    assert len(analysis.flags) >= 1
    assert analysis.summary != ""
    # No flag should have confidence="high" and category="condition"
    # without a note that uses hedging language
    for flag in analysis.flags:
        if flag.category == "condition":
            assert any(
                word in flag.note.lower()
                for word in ["appears", "may", "possible", "visible", "suggests"]
            ), f"Flag note lacks hedging language: {flag.note}"
```

### Cost estimate test

```python
def test_cost_estimate_6_images():
    """Rough token count check — ensure a 6-image batch stays under 20k tokens."""
    # 6 images at 1080px × 1920px each ≈ 6 × 2000 tokens = 12,000 image tokens
    # Prompt ≈ 500 tokens, response ≈ 600 tokens
    # Total ≈ 13,100 tokens
    # At Haiku input rate: 13,100 / 1,000,000 × $0.25 = $0.003
    assert estimated_token_cost(n_images=6, model="claude-haiku-4-5-20251001") < 0.01
```

### Integration test (requires live API key and image URLs)

```bash
export ANTHROPIC_API_KEY=<key>
uv run pytest tests/skills/test_image_analysis.py -m integration -v
# Expected: ImageAnalysis returned with at least 1 flag, source="estimated"
# Expected: No flag has note without hedging language
# Expected: analysis_date is today's date
```

---

## Open Questions

1. **Floor plan detection reliability.** URL heuristics for floor plans
   ("floorplan", "fp_", "floor-plan" in the URL) will miss floor plans with opaque
   CDN URLs. A backup approach is to send the image to the model and ask it to
   self-classify before analysis. Is the latency and cost overhead of a pre-check
   call worth it?

2. **Image ordering.** H2C listings may have a primary image and additional images.
   The primary image is most important (usually the main front-of-house shot or main
   reception room). Should the primary image always be included regardless of `max_images`,
   even if it means reducing the count of interior shots?

3. **Private image URLs.** Some property portal images (Rightmove, Zoopla) are
   behind CDN auth. Will H2C image URLs be publicly accessible, or will the image
   fetcher need to pass auth headers? This affects whether base64 encoding or URL
   references are used in the prompt.

4. **Hedging language enforcement.** The prompt instructs the model to use hedging
   language, but there is no post-processing validation that it has done so. Should
   the harness apply a regex check on flag notes and strip or flag any that make
   definitive statements without hedging?

5. **Consent for image analysis.** The buyer's listing photos are being sent to an
   external LLM API. H2C images are hosted by H2C, not by the buyer, but privacy
   considerations still apply. Should there be an explicit `--enable-image-analysis`
   flag rather than running automatically?

6. **Vision model quality vs cost.** Haiku is much cheaper but may miss subtle
   condition issues (early damp, hairline cracks). Sonnet is better but 12× the
   cost. Should the harness default to Haiku but offer a `--detailed-images` flag
   that uses Sonnet for the top listing only?

7. **False positive rate.** If the model frequently flags "possible damp" in
   listings that are actually fine, buyers will lose trust in the feature. Should
   there be a feedback mechanism ("was this flag accurate?") to detect and tune
   the prompt over time?
