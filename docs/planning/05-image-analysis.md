# 05 - Listing Image Analysis

## Purpose

Property photos can reveal useful triage signals: apparent condition issues, natural
light, room size, garden quality, layout oddities, or mismatches between marketing copy
and visible evidence. The harness should support image analysis as optional advisory
enrichment without depending on one listing portal, image host, model provider, or country.

Image analysis must be cautious. It is not a survey, inspection, valuation, or proof of a
property condition.

## Harness Contract

Image analysis should accept:

- Listing ID and image URLs or image bytes.
- Optional image ordering hints, such as primary image or room labels.
- Maximum image count.
- Optional model/provider preference.

It should return:

- Summary observations.
- Positive visible features.
- Cautious condition or layout warnings.
- Per-image flags with confidence.
- Images analyzed and images skipped.
- Model/provider provenance.
- Analysis date.
- Error or warning details.

The listing remains usable if image analysis is unavailable.

## LLM Responsibilities

The LLM should:

- Describe only visible evidence.
- Use hedging language for uncertain observations.
- Avoid structural, legal, health, or valuation conclusions.
- Avoid subjective decor judgments unless the buyer explicitly asks.
- Flag poor image quality or insufficient coverage.
- Preserve the distinction between visible observation and factual claim.

Example language: "appears to show", "may indicate", "visible in image 2", "worth checking
at viewing". Avoid: "the property has damp" or "the roof needs replacing".

## Suggested Data Shape

```python
@dataclass(frozen=True)
class ImageFlag:
    category: str
    label: str
    confidence: str
    image_index: int | None
    note: str
    source: SourceLabel = "estimated"


@dataclass(frozen=True)
class ImageAnalysis:
    listing_id: str
    summary: str
    flags: list[ImageFlag]
    positive_highlights: list[str]
    condition_warnings: list[str]
    images_analysed: list[str]
    images_skipped: int
    model_used: str
    analysis_date: str
    source: SourceLabel = "estimated"
    error: str | None = None
```

## Adapter Pattern

Separate image retrieval from model analysis:

```python
class ImageFetcher(Protocol):
    def fetch(self, url: str) -> bytes | None: ...


class VisionAnalyzer(Protocol):
    name: str

    def analyse(self, listing: Listing, images: list[bytes]) -> ImageAnalysis:
        ...
```

This allows deployments to use Anthropic, OpenAI, local vision models, platform-provided
image analysis, or no vision provider at all.

## Implementation Guidance

- Make image analysis opt-in or clearly configured; image URLs may be sent to external
  model providers.
- Limit image count and size.
- Skip obvious floor plans, maps, logos, and duplicate images where possible.
- Validate model output for allowed categories and confidence labels.
- Post-process condition warnings to require cautious language.
- Do not let advisory image flags automatically reduce ranking score unless the product
  explicitly chooses that behavior.

## Platform Integration

A listing platform may provide image URLs, image metadata, or previously stored analysis.
Treat those as optional adapter inputs:

- Read available image URLs into `Listing.image_urls`.
- Reuse fresh prior analysis where provenance is clear.
- Write analysis back only if the platform supports it and the user/deployment permits it.

HomesToCompare image fields are one possible source, not a core requirement.

## Testing Focus

- Listings with no images return a graceful analysis error.
- Oversized or inaccessible images are skipped.
- Model output is parsed and normalized.
- Condition warnings use cautious language.
- Source is always `estimated` unless analysis came from a trusted external evidence
  source with its own provenance.
- The harness works normally without a vision provider.

## Open Questions

- Should image analysis be enabled by default for local CSV runs, or always require a flag?
- Should primary images always be included before secondary images?
- Should user feedback on false positives be stored for future prompt tuning?
