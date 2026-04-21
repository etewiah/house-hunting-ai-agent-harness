# 03 - Area Intelligence Enrichment

## Purpose

Buyers often care about area-level facts that individual listing pages do not reliably
cover: schools, safety, flood or climate risk, broadband, transport, amenities, taxes,
noise, walkability, local rules, and future development. These categories vary heavily by
country and region, so the harness should not hardcode one jurisdiction's data sources.

This feature defines a generic area-intelligence capability. It lets an intelligent agent
or deployment choose appropriate local data providers while keeping the harness contract
portable.

## Harness Contract

Area enrichment should accept:

- Listing location: coordinates, address, postcode/ZIP, parcel ID, neighbourhood, or
  another locally meaningful identifier.
- Buyer priorities from the brief.
- Requested categories, or `None` to let the agent choose relevant categories.
- Optional jurisdiction hints.

It should return category-level evidence:

- Category name.
- Summary value.
- Source/provider.
- Jurisdiction or coverage area.
- Retrieval date.
- Confidence or freshness indicator.
- Warnings and limitations.
- Raw details where useful.

The harness should support partial enrichment. One failed category should not block other
categories or the listing workflow.

## LLM Responsibilities

The LLM should:

- Select area categories that match the buyer's stated concerns.
- Prefer authoritative, local, and current sources where available.
- Identify jurisdiction limits before making claims.
- Label estimates and stale data clearly.
- Avoid turning proxy data into definitive claims.
- Avoid discriminatory or protected-class reasoning.

Examples: if a buyer asks for schools, the LLM should look for locally appropriate school
data. If a buyer asks about climate risk, it should use relevant regional hazard sources.
If no reliable local source exists, it should say so.

## Suggested Data Shape

```python
@dataclass(frozen=True)
class AreaEvidence:
    category: str
    summary: str
    source_name: str
    source: SourceLabel
    retrieved_at: str
    jurisdiction: str | None = None
    confidence: str | None = None
    details: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AreaData:
    listing_id: str
    evidence: list[AreaEvidence]
    warnings: list[str] = field(default_factory=list)
```

Provider-derived data should not be labelled as `listing_provided` unless it came directly
from the listing source. Prefer `estimated`, `inferred`, or add a provider-specific source
name.

## Adapter Pattern

```python
class AreaDataProvider(Protocol):
    name: str
    categories: set[str]

    def supports(self, location: object, jurisdiction: str | None = None) -> bool:
        ...

    def fetch(self, listing: Listing, categories: list[str]) -> AreaData:
        ...
```

Deployments can register providers for their geography. The core harness should operate
on normalized `AreaData`, not on provider-specific schemas.

## Example Categories

These are examples, not mandatory categories:

- Education: school ratings, catchment indicators, admissions caveats.
- Safety: crime statistics, emergency response data, local warnings.
- Environment: flood, wildfire, heat, air quality, noise, contamination.
- Connectivity: broadband, mobile coverage, transport access.
- Amenities: groceries, parks, healthcare, childcare, fitness, cultural venues.
- Costs and rules: taxes, HOA/service charges, rent controls, local restrictions.
- Market context: listing age, price history, comparable sales where available.

Each category must carry provenance and coverage limitations.

## Platform Integration

If a platform such as HomesToCompare already stores area data, the harness may use it as a
cache or persistence layer. This should be optional:

- Read existing platform evidence when available.
- Check freshness before trusting cached values.
- Write enriched data back only through an explicit platform adapter.
- Continue to work without platform access.

## Implementation Guidance

- Start with a small generic `AreaEvidence` model instead of many region-specific
  dataclasses.
- Fetch only categories relevant to the buyer or requested by the caller.
- Make enrichment lazy for top results unless ranking explicitly depends on it.
- Keep provider-specific API details in adapters or regional notes, not in core docs.
- Include privacy controls before sending precise locations to third-party services.

## Testing Focus

- Unsupported jurisdictions return warnings, not false data.
- Partial failures preserve successful categories.
- Provider-derived data includes source, jurisdiction, and retrieval date.
- Ranking only uses area data when rules are clear and non-discriminatory.
- The LLM surfaces limitations in summaries.

## Open Questions

- Which area categories should be allowed to influence numeric ranking?
- Should the harness include a consent gate before precise-location enrichment?
- Should deployments provide regional provider packs outside the core harness?
