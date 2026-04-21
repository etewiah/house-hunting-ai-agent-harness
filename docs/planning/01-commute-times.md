# 01 - Commute and Travel Time Enrichment

## Purpose

The harness should help a buyer understand how each property affects day-to-day travel.
Commute time is often more important than small differences in price or finish, but the
harness must not assume a particular city, country, transport network, or routing API.

This feature defines a provider-agnostic commute capability. Local deployments can use
whatever routing data is appropriate: Google Maps, Apple Maps, regional transit APIs,
OpenStreetMap-based services, a platform-native connector, or even a manually supplied
estimate. The harness only requires a consistent contract, clear provenance, and graceful
failure when data is unavailable.

## Harness Contract

For each listing, the commute capability should accept:

- Listing location: address, postcode/ZIP, coordinates, or a locally meaningful place ID.
- Destination: the buyer's workplace, school, station, city centre, or other travel hub.
- Mode: transit, driving, walking, cycling, mixed, or provider default.
- Optional assumptions: departure time, arrival time, weekday/weekend, accessibility needs.

It should return:

- Duration in minutes, or `None` if unavailable.
- Mode actually used.
- Source/provider name.
- Retrieval timestamp.
- Confidence or quality indicator where possible.
- Warnings explaining gaps, approximations, or coverage limits.

The ranking system should only treat commute data as meaningful when the result includes
enough provenance to explain where it came from.

## LLM Responsibilities

The LLM using the harness should:

- Infer commute destinations and preferred modes from the buyer brief when possible.
- Ask a concise follow-up only when travel requirements are central and ambiguous.
- Choose the best available commute provider for the buyer's geography.
- Explain missing or approximate commute data rather than hiding it.
- Avoid presenting estimated travel times as guaranteed journey times.

The LLM may use local knowledge or web research to identify suitable providers, but any
computed result should be attached to the structured commute contract above.

## Suggested Data Shape

```python
@dataclass(frozen=True)
class CommuteEstimate:
    listing_id: str
    destination: str
    duration_minutes: int | None
    mode: str
    provider: str
    source: SourceLabel
    retrieved_at: str
    confidence: str | None = None
    warnings: list[str] = field(default_factory=list)
```

Listings can then carry the most relevant commute estimate, or a list if multiple modes
or destinations are compared.

## Adapter Pattern

Implement commute providers behind a small interface:

```python
class CommuteProvider(Protocol):
    name: str

    def estimate(
        self,
        listing: Listing,
        destination: str,
        mode: str | None = None,
        assumptions: dict | None = None,
    ) -> CommuteEstimate:
        ...
```

Provider selection should be configuration-driven or LLM-directed. A deployment may
register one provider or many. The harness should not embed geography-specific logic in
the core ranking code.

## Implementation Guidance

- Enrich listings before ranking if commute is part of the buyer's requirements.
- If enrichment happens after ranking, re-rank or clearly state that ranking used missing
  commute data.
- Cache results where provider terms allow it.
- Preserve raw provider identifiers only where useful for debugging; do not make the core
  schema depend on one provider's response format.
- Avoid surprise costs by requiring explicit configuration for paid providers.

## Examples, Not Requirements

- In London, a deployment might use TfL for public transport.
- In many regions, Google Maps or Apple Maps may be the most complete option.
- In OpenStreetMap-friendly deployments, OpenRouteService or OSRM may handle walking,
  cycling, or driving.
- In a low-data area, a user-supplied estimate may be better than pretending precision.

These are implementation examples. They should not constrain where the harness can run.

## Testing Focus

- Missing location data returns a clear warning, not an exception.
- Provider failures leave listings usable.
- Ranking changes when reliable commute data becomes available.
- Paid providers are not called unless explicitly configured.
- Cached and live results expose their provenance consistently.

## Open Questions

- Should the buyer profile store multiple destinations, such as work and school?
- Should commute assumptions default to peak weekday travel, or remain provider-defined?
- Should ranking use commute estimates with low confidence, or only surface them as notes?
