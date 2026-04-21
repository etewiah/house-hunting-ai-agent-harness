# 01 — Real Commute Times

## Goal

`commute_minutes` in the `Listing` dataclass is currently populated only in the mock
dataset, where values are hardcoded integers with no relationship to the listing's
actual address. For a real buyer, commute time is often the single deciding factor
between shortlisted properties — a house that saves £50k but adds 40 minutes each way
costs far more over a working lifetime. When a buyer states "max 45 minutes to King's
Cross", they deserve a real answer, not a placeholder.

The feature removes the mock by enriching each candidate listing with a live routing
call. The buyer's `location_query` (already in `BuyerProfile`) is treated as the
commute destination hub. Each listing's address is geocoded to a lat/lng pair, then a
routing API resolves the actual door-to-hub travel time by the buyer's preferred mode
(default: public transport + walking, reflecting UK house-buying reality). The enriched
`commute_minutes` is stored back against the listing so the ranking engine
(`src/skills/ranking.py`) can use it meaningfully — a listing that was penalised only
because commute data was missing will now be scored correctly.

---

## HomesToCompare Integration

H2C is relevant at three points in the commute enrichment pipeline:

**1. Source of listing addresses.**
The `_row_to_listing` mapper in `src/connectors/homestocompare_connector.py` currently
ignores the `address`, `postcode`, and `lat`/`lng` fields that H2C returns. These need
to be mapped into the `Listing` dataclass so the commute enricher has something to
geocode. If lat/lng are already present in the row, geocoding can be skipped entirely.

**2. Write-back of enriched data.**
Once commute times are resolved, the harness can POST them back to H2C via a new
`/api/house-hunt/enrich-listing` endpoint (to be built on the H2C side). This means
the next buyer who views the same listing from H2C gets the cached result without
triggering another routing call. This is optional for Phase 1 but important for
avoiding redundant API spend at scale.

**3. Display on H2C comparison pages.**
H2C comparison pages at `/pc/[suid_code]/details` already show listing attributes.
If `commute_minutes` is populated and attributed correctly, H2C can surface it in the
comparison UI without any harness involvement after the initial enrichment.

---

## External APIs / Services

### TfL Journey Planner API
- URL: https://api.tfl.gov.uk/journey/journeyresults/{from}/to/{to}
- Cost: **Free** with registration; rate limit 500 req/min per API key
- Coverage: **London only** (all TfL modes including Tube, Overground, Elizabeth line,
  bus, cycling)
- Best for: London-centric buyers commuting within Greater London
- Notes: Returns itineraries with multiple legs. Parse `duration` from the first
  `journey` object. Accepts National Rail station names or lat/lng as `from`/`to`.
- Registration: https://api-portal.tfl.gov.uk/

### Google Maps Distance Matrix API
- URL: https://maps.googleapis.com/maps/api/distancematrix/json
- Cost: **Paid**. $0.005 per element (origin+destination pair), $0.01 per element for
  transit. Free tier: $200/month credit (~20,000 transit calls/month).
- Coverage: Global
- Best for: Non-London UK cities (Manchester, Bristol, Leeds, Edinburgh, Birmingham)
- Notes: `mode=transit` returns public transport duration including walking legs.
  Response includes `duration.value` in seconds. Needs geocoding step first unless
  address strings are accurate enough for the API's internal geocoder.

### Mapbox Matrix API
- URL: https://api.mapbox.com/directions-matrix/v1/mapbox/{profile}
- Cost: **Paid**. $0.001 per element for driving/walking/cycling. No public transit
  mode (driving proxy only).
- Coverage: Global
- Best for: Driving commute estimates only. Not suitable as primary option for UK
  buyers (most commute by rail/tube).

### Openrouteservice (ORS)
- URL: https://api.openrouteservice.org/v2/directions/{profile}
- Cost: **Free tier** (2,000 req/day, 40 req/min). Self-hostable on Docker with no
  rate limits.
- Coverage: Global (OpenStreetMap data)
- Modes: `driving-car`, `foot-walking`, `cycling-regular`. No public transit.
- Best for: walking/cycling commute times, or as a free fallback when budget is
  constrained. Self-hosted option suits privacy-conscious deployments.
- Docs: https://openrouteservice.org/dev/#/api-docs

### Postcodes.io (geocoding)
- URL: https://postcodes.io/postcodes/{postcode}
- Cost: **Free**, no key required
- Coverage: England, Scotland, Wales
- Returns: `latitude`, `longitude`, admin district, ward
- Best for: geocoding UK postcodes to lat/lng before passing to routing APIs

### Google Maps Geocoding API
- URL: https://maps.googleapis.com/maps/api/geocode/json
- Cost: $0.005 per request. Free tier via $200/month credit.
- Best for: full-address geocoding when postcode alone is not available

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
    # New fields
    address: str | None = None          # Full address string, may include postcode
    postcode: str | None = None         # UK postcode, used for Postcodes.io geocoding
    latitude: float | None = None       # WGS84; populated from H2C row or geocoding
    longitude: float | None = None      # WGS84; populated from H2C row or geocoding
    commute_mode: str | None = None     # "transit", "driving", "walking", "cycling"
    commute_source: SourceLabel = "missing"  # provenance of commute_minutes
```

### New `CommuteResult` dataclass

```python
@dataclass(frozen=True)
class CommuteResult:
    listing_id: str
    origin_lat: float
    origin_lng: float
    destination: str          # The buyer's location_query string
    destination_lat: float
    destination_lng: float
    duration_minutes: int
    mode: str                 # "transit", "driving", "walking"
    provider: str             # "tfl", "google_maps", "ors"
    raw_response: dict        # Full API response, stored for debugging/caching
    error: str | None = None  # Set if the call failed; listing keeps commute_minutes=None
```

### New `GeocodedAddress` dataclass

```python
@dataclass(frozen=True)
class GeocodedAddress:
    query: str              # Input: address string or postcode
    lat: float
    lng: float
    normalised: str         # Canonical address returned by geocoder
    provider: str           # "postcodes_io", "google_geocoding"
    confidence: float       # 0.0–1.0; postcodes.io is always 1.0 for exact matches
```

---

## New Files to Create

```
src/skills/commute.py
```
Core skill: geocodes a listing address and calls the appropriate routing API to
return a `CommuteResult`. Selects provider based on `COMMUTE_PROVIDER` env var.

```
src/connectors/tfl_connector.py
```
TfL Journey Planner HTTP client. Handles lat/lng and station-name inputs.

```
src/connectors/google_maps_connector.py
```
Google Distance Matrix + Geocoding HTTP client. Shared session with retry logic.

```
src/connectors/ors_connector.py
```
Openrouteservice HTTP client for driving/walking/cycling. Respects rate limits.

```
src/connectors/postcodes_io_connector.py
```
Free UK postcode geocoder. No authentication required.

```
tests/skills/test_commute.py
```
Unit and integration tests for the commute enrichment skill.

```
tests/connectors/test_tfl_connector.py
```
Recorded HTTP fixture tests for the TfL Journey Planner connector.

---

## Changes to Existing Files

### `src/models/schemas.py`
- Add `address`, `postcode`, `latitude`, `longitude`, `commute_mode`,
  `commute_source` fields to `Listing` (all optional, default `None`).
- Add `CommuteResult` and `GeocodedAddress` dataclasses.
- `Listing` remains `frozen=True`; new fields use `field(default=None)`.

### `src/connectors/homestocompare_connector.py`
- Update `_row_to_listing` to map `postcode`, `address`, `lat`/`latitude`,
  `lng`/`longitude` from the H2C API response row.
- Add `enrich_commute(listing_id, commute_result)` method to
  `HomesToCompareConnector` to POST enriched commute data back to H2C.

### `src/harness/orchestrator.py`
- Add `enrich_commutes(mode: str = "transit")` method. Iterates over
  `self.state.ranked_listings`, calls `commute.resolve_commute()` for each,
  replaces the `Listing` with an enriched copy (using `dataclasses.replace`),
  and records results in the trace.
- Call `enrich_commutes()` from within `triage()` if a commute provider is
  configured (controlled by env var `COMMUTE_PROVIDER`).

### `src/harness/session_state.py`
- Add `commute_results: list[CommuteResult]` field (default empty list).

### `src/connectors/mock_listing_api.py`
- Remove hardcoded `commute_minutes` values from mock data. Replace with
  `commute_minutes=None` and add `postcode` values so the mock can be used
  with real geocoding in integration tests.

### `src/skills/ranking.py`
- No logic changes needed — it already handles `commute_minutes=None` with
  a warning. The enrichment step feeds it populated values before ranking runs.

---

## MCP Server Tools

Add to `src/ui/mcp_server.py`:

```python
@mcp.tool()
def enrich_commute_times(
    listings: list[dict],
    destination: str,
    mode: str = "transit",
) -> list[dict]:
    """Resolve real commute times for a list of listings.

    Geocodes each listing's address/postcode and calls the configured routing
    API (TfL for London, Google Maps for other UK cities, ORS for
    walking/cycling). Adds commute_minutes, commute_mode, and commute_source
    to each listing dict.

    Args:
        listings: List of listing dicts. Each must have at least one of:
                  postcode (str), address (str), latitude+longitude (float).
        destination: Commute hub, e.g. "King's Cross", "Manchester Piccadilly",
                     or a postcode like "EC1A 1BB".
        mode: "transit" (default), "driving", "walking", or "cycling".

    Returns:
        Same list with commute_minutes, commute_mode, commute_source added.
        Listings where geocoding failed will have commute_minutes=null and
        commute_source="missing".
    """
    ...
```

```python
@mcp.tool()
def geocode_address(address: str) -> dict:
    """Geocode a UK address or postcode to latitude/longitude.

    Tries Postcodes.io first (free, exact for postcodes), then falls back to
    Google Geocoding if available.

    Returns: {lat, lng, normalised, provider, confidence}
    """
    ...
```

---

## Implementation Phases

### Phase 1 — Geocoding pipeline (no routing)
**Deliverable:** Listings from H2C have `latitude`/`longitude` populated.

- Update `_row_to_listing` to read `lat`, `lng`, `postcode`, `address` from H2C rows.
- Implement `src/connectors/postcodes_io_connector.py` with
  `geocode_postcode(postcode: str) -> GeocodedAddress`.
- Add `geocode_listing(listing: Listing) -> Listing` in `src/skills/commute.py`
  that returns an enriched copy via `dataclasses.replace`.
- Unit test: input `{"postcode": "N1 9GU"}` → lat ~51.53, lng ~-0.10.
- No routing calls yet; `commute_minutes` remains `None`.

### Phase 2 — TfL routing (London)
**Deliverable:** London listings get real commute times via TfL API.

- Implement `src/connectors/tfl_connector.py`:
  `get_journey_time(origin_lat, origin_lng, destination: str) -> int | None`.
- Update `src/skills/commute.py` to call TfL when destination resolves to a
  London station or postcode within Greater London.
- Add `enrich_commutes()` to `HouseHuntOrchestrator`.
- MCP tool `enrich_commute_times` implemented and tested.
- CLI: if `COMMUTE_PROVIDER=tfl` is set, commute enrichment runs automatically
  after triage.

### Phase 3 — Google Maps for non-London
**Deliverable:** Manchester, Bristol, Leeds, Edinburgh listings get commute times.

- Implement `src/connectors/google_maps_connector.py` with Distance Matrix and
  Geocoding clients.
- Provider selection logic in `src/skills/commute.py`:
  - `COMMUTE_PROVIDER=tfl` → TfL always
  - `COMMUTE_PROVIDER=google` → Google always
  - `COMMUTE_PROVIDER=auto` → TfL if destination is within M25, Google otherwise
- Write-back to H2C via `HomesToCompareConnector.enrich_commute()`.

### Phase 4 — ORS fallback + caching
**Deliverable:** Walking/cycling modes, no-cost fallback, local result cache.

- Implement `src/connectors/ors_connector.py` for walking/cycling modes.
- Add a simple file-based cache in `~/.house-hunt/commute_cache.json` keyed by
  `(postcode, destination, mode)`. TTL: 7 days.
- Expose `COMMUTE_CACHE_TTL_DAYS` env var.
- Avoid redundant API calls when the same listing is ranked across multiple
  sessions.

---

## Testing Plan

### Unit tests

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_postcodes_io_geocode_valid` | postcode `"SW1A 1AA"` | lat ~51.501, lng ~-0.141 |
| `test_postcodes_io_geocode_invalid` | postcode `"ZZ9 9ZZ"` | raises `GeocodingError` |
| `test_tfl_parse_duration` | raw TfL JSON fixture | `CommuteResult.duration_minutes == 32` |
| `test_commute_enrichment_replaces_listing` | `Listing(commute_minutes=None, postcode="N1 9GU")` | returns new `Listing` with `commute_minutes=28, commute_source="estimated"` |
| `test_provider_auto_selects_tfl` | destination `"King's Cross"` | provider `"tfl"` |
| `test_provider_auto_selects_google` | destination `"Manchester Piccadilly"` | provider `"google_maps"` |
| `test_ranking_uses_enriched_commute` | `BuyerProfile(max_commute_minutes=30)`, listing with enriched `commute_minutes=28` | listing `matched` list includes `"commute requirement"` |
| `test_ranking_warns_on_missing_commute` | same profile, listing with `commute_minutes=None` | listing `warnings` includes `"commute time missing"` |

### Integration tests (require live API keys)

```bash
# Set up
export COMMUTE_PROVIDER=tfl
export TFL_APP_KEY=<your_key>

# Run integration test
uv run pytest tests/connectors/test_tfl_connector.py -m integration -v

# Expected: at least one journey from SW1A 1AA to King's Cross under 40 minutes
```

### End-to-end smoke test

```bash
uv run house-hunt demo
# Should show commute_minutes populated for London listings (not "?")
# Should show commute_source="estimated" attribution in trace output
```

---

## Open Questions

1. **Address quality.** H2C listing rows may have incomplete addresses — just a
   town name, no postcode. What is the guaranteed minimum address data available from
   the H2C API? Can postcode always be relied on, or do we need full-address geocoding
   as the primary path?

2. **TfL destination resolution.** The buyer writes "King's Cross" in their brief.
   TfL Journey Planner accepts station naptan IDs, lat/lng, or text. Should we
   maintain a small lookup table of common London stations to naptan IDs, or always
   geocode the destination string too?

3. **Provider cost policy.** Who bears the cost of Google Maps calls — the harness
   operator or the end user? Should the MCP tool refuse to run if `COMMUTE_PROVIDER`
   is not explicitly set, to prevent surprise API charges?

4. **Commute mode default.** UK buyers mostly use rail/tube but some drive. Should
   the `BuyerProfile` gain a `preferred_commute_mode` field, or should mode be an
   argument at the tool call level?

5. **Caching granularity.** The cache key proposal is `(postcode, destination, mode)`.
   Should `destination` be normalised (lowercased, stripped) before hashing to avoid
   cache misses from minor string differences? Who is responsible for normalisation?

6. **TfL rate limits in bulk.** With 200 candidate listings (the `H2CListingConnector`
   default limit), 200 TfL routing calls could take several minutes. Should enrichment
   run concurrently with `asyncio`, and if so, does the MCP server need to be made
   async-compatible?

7. **H2C write-back authorisation.** The `HomesToCompareConnector` uses a single
   `x-h2c-harness-key` for both reads and writes. Should commute write-back require a
   separate elevated key to prevent any harness operator from writing arbitrary data
   to H2C listing records?
