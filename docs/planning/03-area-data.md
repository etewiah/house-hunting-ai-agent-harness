# 03 — Area Data Enrichment

## Goal

A buyer's brief frequently contains area-level concerns that individual listing pages
cannot address: "good school catchment", "low crime", "not prone to flooding", "fast
broadband for working from home". Today the harness ignores all of these. The listing
features list (`Listing.features`) may contain agent-supplied strings like "good
schools nearby" but these are marketing copy, not data.

This feature enriches every shortlisted listing with verified, government-sourced area
data:

- **Schools:** Ofsted-rated schools within a configurable radius, with ratings
- **Crime:** Police-recorded crime rate by category for the listing's postcode sector
- **Flood risk:** Environment Agency flood zone classification for the property
- **Broadband:** Ofcom median download speed for the postcode
- **Transport:** TfL Public Transport Accessibility Level (PTAL) score for London

The enriched data is stored in a new `AreaData` schema, attached to each `Listing`,
and surfaced in three places: the CLI output, the MCP tool response, and (eventually)
the HomesToCompare listing page. Crucially, all area data is clearly labelled with its
source and a retrieval date, because it is point-in-time data that changes.

The harness should not duplicate data that H2C already surfaces on its listing pages.
The intent is complementary enrichment: the harness pre-fetches area data so that
the buyer has it before making a viewing decision, not after.

---

## HomesToCompare Integration

H2C listing pages may already surface some area information (Ofsted, broadband,
flood risk). The harness connector should check what H2C already provides via the
`/for-the-ai` endpoint before making redundant external API calls.

Workflow:
1. Call `GET /pc/[suid_code]/for-the-ai` to read any existing area data H2C has
   stored for the listing.
2. For each data category, if H2C already has a fresh value (within 30 days), use it.
3. For categories H2C does not have, call the external API and store the result.
4. POST the enriched `AreaData` back to H2C via an extended
   `/api/house-hunt/enrich-listing` endpoint so future users benefit from the cached
   data.

This positions the harness as a data enrichment contributor to H2C, not just a
consumer. H2C becomes a shared cache of area intelligence that all users of the
platform benefit from.

---

## External APIs / Services

### Ofsted API
- URL: https://api.ofsted.gov.uk/v1/get-links
- Cost: **Free** with API key registration
- Data: inspection reports, ratings (Outstanding/Good/Requires Improvement/Inadequate)
  for schools, early years, further education
- Coverage: England only
- Limitations: The public API provides links to inspection reports; structured
  ratings by postcode require the GIAS (Get Information About Schools) API.

### Get Information About Schools (GIAS)
- URL: https://get-information-schools.service.gov.uk/api
- Cost: **Free**, no key required for basic queries
- Endpoint: `GET /api/schools?postCode={postcode}&RadiusInMiles=0.5`
- Data: school name, type, phase, URN, Ofsted rating, address
- Coverage: England only
- Notes: Pagination required; returns up to 25 schools per page.
  Wales schools are in a separate register (https://mylocalschool.gov.wales).

### data.police.uk API
- URL: https://data.police.uk/api/crimes-at-location
- Cost: **Free**, no key required
- Endpoints:
  - `GET /api/crimes-at-location?lat={lat}&lng={lng}&date={yyyy-mm}`
  - `GET /api/crime-categories`
- Data: crime category, month, street-level location
- Coverage: England, Wales, and Scotland
- Limitations: Data is 2–4 months behind real-time. Returns individual crime events
  (not rates), so the harness must aggregate over a 12-month window.

### Environment Agency Flood Map API
- URL: https://environment.data.gov.uk/flood-monitoring/id/floodAreas
- Cost: **Free**
- Flood zones endpoint: `GET /api/floodareas?polygon=...` or by flood area ID
- Better endpoint: `GET https://check-flooding.service.gov.uk/api/property/{postcode}`
  (not officially documented but returns zone 1/2/3 classification reliably)
- Coverage: England only. Scotland: SEPA (https://www.sepa.org.uk/). Wales: NRW.
- Alternative: Long-Term Flood Risk API (LTFR):
  `GET https://environment.data.gov.uk/arcgis/rest/services/EA/FloodMapForPlanningRiversAndSea/MapServer/1/query?geometry={lng},{lat}&f=json`

### Ofcom Connected Nations API
- URL: https://api.ofcom.org.uk/connected-nations
- Cost: **Free** with API key (obtainable from https://developer.ofcom.org.uk/)
- Endpoint: `GET /connected-nations/broadband-coverage/{postcode}`
- Data: download/upload speeds, technology (FTTC/FTTP/cable/5G), provider coverage
- Coverage: UK-wide
- Notes: Returns postcode-level averages, not property-specific. FTTP availability
  (full-fibre) is the most buyer-relevant field.

### TfL PTAL (Public Transport Accessibility Level)
- URL: https://api.tfl.gov.uk/TransportDemand/AccesibilityLevel
- Actually the correct endpoint:
  `GET https://api.tfl.gov.uk/place?lat={lat}&lon={lng}&radius=500&type=StopPoint`
  used to compute PTAL score manually, or use the TfL accessibility data download.
- Cost: **Free** with TfL API key
- Coverage: London only (PTAL scores are London-specific)
- Alternative: TfL's PTAL grid is available as a static download; a local lookup is
  more reliable than live API for this use case.
- Notes: PTAL scores range 0–6b. Score ≥3 is generally considered acceptable for
  car-free living.

---

## Data Model Changes

### New `SchoolInfo` dataclass

```python
@dataclass(frozen=True)
class SchoolInfo:
    name: str
    type: str               # "Primary", "Secondary", "Academy", etc.
    ofsted_rating: str | None  # "Outstanding", "Good", "RI", "Inadequate", None
    distance_metres: int
    urn: str                # Unique Reference Number from GIAS
    source: SourceLabel     # Always "listing_provided" from GIAS data
    retrieved_date: str     # ISO date string, e.g. "2026-04-21"
```

### New `CrimeSummary` dataclass

```python
@dataclass(frozen=True)
class CrimeSummary:
    postcode_sector: str        # e.g. "N1 9"
    period_months: int          # Number of months aggregated (typically 12)
    total_crimes: int
    by_category: dict[str, int] # {"violent-crime": 12, "burglary": 3, ...}
    relative_rate: str | None   # "low" | "average" | "high" compared to borough avg
    source: SourceLabel         # Always "listing_provided" from data.police.uk
    retrieved_date: str
```

### New `FloodRisk` dataclass

```python
@dataclass(frozen=True)
class FloodRisk:
    postcode: str
    flood_zone: str | None      # "1" (low), "2" (medium), "3a" (high), "3b" (floodplain)
    surface_water_risk: str | None  # "very low" | "low" | "medium" | "high"
    source: SourceLabel         # Always "listing_provided" from EA API
    retrieved_date: str
    coverage: str               # "england" | "scotland" | "wales" | "unknown"
    note: str | None            # e.g. "Data unavailable for Scotland"
```

### New `BroadbandData` dataclass

```python
@dataclass(frozen=True)
class BroadbandData:
    postcode: str
    median_download_mbps: float | None
    median_upload_mbps: float | None
    fttp_available: bool | None     # Full-fibre to the premises
    max_download_mbps: float | None # Best available at postcode
    source: SourceLabel             # Always "listing_provided" from Ofcom API
    retrieved_date: str
```

### New `TransportAccessibility` dataclass

```python
@dataclass(frozen=True)
class TransportAccessibility:
    ptal_score: str | None       # "0"–"6b" for London, None outside London
    nearest_stations: list[str]  # Up to 3 nearest rail/tube station names
    walk_minutes_to_nearest: int | None
    source: SourceLabel          # "listing_provided" (TfL) or "estimated" (derived)
    retrieved_date: str
```

### New `AreaData` dataclass

```python
@dataclass(frozen=True)
class AreaData:
    listing_id: str
    postcode: str
    schools: list[SchoolInfo]                  # Up to 5 nearest schools
    crime: CrimeSummary | None
    flood_risk: FloodRisk | None
    broadband: BroadbandData | None
    transport: TransportAccessibility | None
    enrichment_warnings: list[str]             # e.g. "Flood data unavailable outside England"
```

### Extended `Listing` dataclass

```python
@dataclass(frozen=True)
class Listing:
    ...
    area_data: AreaData | None = None    # Populated after enrichment step
```

---

## New Files to Create

```
src/skills/area_enrichment.py
```
Orchestrates all area data fetches for a given listing. Checks H2C cache first,
dispatches to connectors, assembles `AreaData`, handles partial failures gracefully.

```
src/connectors/gias_connector.py
```
GIAS school search HTTP client. Paginates results and normalises Ofsted rating strings.

```
src/connectors/police_uk_connector.py
```
data.police.uk crime aggregator. Fetches 12 months of crimes, groups by category.

```
src/connectors/environment_agency_connector.py
```
Environment Agency Flood Map API client. Handles England-only coverage gracefully.

```
src/connectors/ofcom_connector.py
```
Ofcom Connected Nations broadband API client.

```
src/connectors/tfl_ptal_connector.py
```
TfL PTAL score lookup. Accepts lat/lng, returns PTAL band.

```
tests/skills/test_area_enrichment.py
```
Unit tests for enrichment orchestration, partial failure handling, cache logic.

```
tests/connectors/test_police_uk_connector.py
```
HTTP fixture tests for crime data aggregation.

```
tests/connectors/test_environment_agency_connector.py
```
HTTP fixture tests for flood zone classification.

---

## Changes to Existing Files

### `src/models/schemas.py`
- Add `SchoolInfo`, `CrimeSummary`, `FloodRisk`, `BroadbandData`,
  `TransportAccessibility`, and `AreaData` dataclasses.
- Add `area_data: AreaData | None = None` to `Listing`.

### `src/harness/orchestrator.py`
- Add `enrich_area_data(listing_ids: list[str] | None = None)` method.
  If `listing_ids` is None, enriches all ranked listings.
  Records `AreaData` objects in `self.state`.
- The method should be non-blocking for categories that fail — partial area data is
  better than none.

### `src/harness/session_state.py`
- Add `area_data: dict[str, AreaData]` field (keyed by listing_id).

### `src/skills/ranking.py`
- Add area-data-aware ranking bonuses (Phase 3): listings with outstanding schools
  +3 points if buyer has "schools" in `must_haves`; listings in Flood Zone 3
  generate a warning appended to `RankedListing.warnings`.

### `src/connectors/homestocompare_connector.py`
- Add `enrich_listing_area(listing_id: str, area_data: AreaData) -> dict` method.
  POSTs area enrichment to H2C's `/api/house-hunt/enrich-listing` endpoint.

### `src/ui/cli.py`
- Add area data display section after the comparison output. Show schools (with
  Ofsted ratings), crime summary (total + worst category), flood zone, and broadband
  speed. Cap display to prevent overwhelming output.

---

## MCP Server Tools

```python
@mcp.tool()
def enrich_area_data(
    listings: list[dict],
    categories: list[str] | None = None,
) -> list[dict]:
    """Fetch area-level data for each listing.

    Retrieves schools (Ofsted ratings), crime rates (data.police.uk),
    flood risk (Environment Agency), broadband speeds (Ofcom), and
    transport accessibility (TfL PTAL for London).

    Each listing must have at least one of: postcode (str), or
    latitude+longitude (float). Listings without location data are returned
    unchanged with an enrichment_warning.

    Args:
        listings: List of listing dicts.
        categories: Optional subset of ["schools", "crime", "flood_risk",
                    "broadband", "transport"]. Fetches all by default.

    Returns:
        Same list with an area_data dict added to each listing.
        area_data contains: schools, crime, flood_risk, broadband, transport,
        enrichment_warnings. Any category that fails is null with a warning.

    Notes:
        - Schools data covers England only (partial Wales support planned).
        - Flood risk covers England only; returns a warning for Scotland/Wales.
        - Crime data covers England, Wales, and Scotland.
        - Transport PTAL scores are London only; other cities return null.
        - All data is point-in-time; retrieved_date is included in each record.
    """
    ...
```

```python
@mcp.tool()
def get_area_summary(listing: dict) -> str:
    """Return a human-readable area summary for a single listing.

    Fetches area data (if not already present in the listing dict) and formats
    it as a short prose paragraph: school quality, crime level, flood risk,
    broadband speed, and transport access.

    Suitable for including in a buyer briefing or comparison narrative.
    Clearly labelled as sourced data, not professional advice.
    """
    ...
```

```python
@mcp.tool()
def check_school_catchment(postcode: str, school_name: str) -> dict:
    """Check whether a postcode is likely within catchment for a named school.

    Uses GIAS distance data as a proxy for catchment likelihood. Returns:
    {school_name, postcode, distance_metres, ofsted_rating, catchment_note}

    catchment_note explains that distance is a proxy only — formal catchment
    boundaries require checking with the local authority.
    """
    ...
```

---

## Implementation Phases

### Phase 1 — Crime and broadband (two simplest APIs)
**Deliverable:** Each ranked listing shows crime rate and broadband speed.

- Implement `src/connectors/police_uk_connector.py`.
  Aggregate 12 months of crime events by postcode sector. Return `CrimeSummary`.
- Implement `src/connectors/ofcom_connector.py`.
  Return `BroadbandData` for a postcode.
- Implement the `AreaData` schema and `area_enrichment.py` skeleton.
  Handle missing postcode gracefully with an `enrichment_warning`.
- CLI output: append crime summary and broadband speed after each listing.
- MCP tool `enrich_area_data` implemented for `categories=["crime", "broadband"]`.

### Phase 2 — Schools
**Deliverable:** Top 3 nearest schools with Ofsted ratings for each listing.

- Implement `src/connectors/gias_connector.py`.
- Schools are only fetched if the buyer's `must_haves` or `nice_to_haves` contain
  "schools" OR `categories` explicitly includes "schools".
- This avoids unnecessary API calls for buyers who have no school interest.
- Ranking bonus: +3 score if buyer needs schools and listing has ≥1 Outstanding school
  within 500m.

### Phase 3 — Flood risk and PTAL
**Deliverable:** Flood zone warnings and London transport scores.

- Implement `src/connectors/environment_agency_connector.py`.
  Return `FloodRisk`. Add `flood_zone` warning to `RankedListing.warnings` if
  zone is 3a or 3b.
- Implement `src/connectors/tfl_ptal_connector.py`.
- Add `transport` category to `enrich_area_data` MCP tool.

### Phase 4 — H2C cache integration
**Deliverable:** Area data is read from and written back to H2C.

- Check `/for-the-ai` endpoint for existing area data before calling external APIs.
- POST enriched `AreaData` to H2C's `/api/house-hunt/enrich-listing`.
- Add `retrieved_date` freshness check: re-fetch if data is older than 30 days.
- Add `get_area_summary` MCP tool (prose summary).

---

## Testing Plan

### Unit tests

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_crime_aggregation_12_months` | 12 fixture response JSONs | `CrimeSummary.total_crimes` equals sum across all months |
| `test_crime_category_grouping` | response with 3 burglary events | `by_category["burglary"] == 3` |
| `test_broadband_fttp_true` | Ofcom response with FTTP available | `BroadbandData.fttp_available == True` |
| `test_broadband_missing_postcode` | Listing with no postcode | `AreaData.enrichment_warnings` contains "no postcode" |
| `test_school_ofsted_normalisation` | GIAS returns "Good" and "GOOD" | both normalise to "Good" |
| `test_flood_zone_3_triggers_warning` | `FloodRisk.flood_zone == "3a"` | `RankedListing.warnings` contains "flood risk zone 3a" |
| `test_flood_data_scotland_graceful` | postcode `"EH1 1AB"` (Edinburgh) | `FloodRisk.coverage == "scotland"`, `note` explains EA limitation |
| `test_area_enrichment_partial_failure` | crime API times out | `area_data.crime == None`, `enrichment_warnings` non-empty, other categories succeed |
| `test_ptal_london_postcode` | lat/lng near Angel, Islington | `ptal_score` not None |
| `test_ptal_manchester_postcode` | lat/lng near Manchester Piccadilly | `ptal_score == None`, no error raised |

### Integration tests (require live APIs — all free)

```bash
# Crime API — no key required
uv run pytest tests/connectors/test_police_uk_connector.py -m integration

# Broadband API — requires OFCOM_API_KEY
export OFCOM_API_KEY=<key>
uv run pytest tests/connectors/test_ofcom_connector.py -m integration

# Schools API — no key required
uv run pytest tests/connectors/test_gias_connector.py -m integration
```

### End-to-end CLI test

```bash
uv run house-hunt demo
# Should show area data section for top 3 listings
# Expected: crime summary present (total_crimes > 0 for demo postcodes)
# Expected: broadband data shows speed or "unavailable"
# Expected: at least 1 school listed for London postcodes
```

---

## Open Questions

1. **H2C duplication.** What area data does H2C currently display on its listing pages?
   Is there an agreed list of categories the harness should own vs categories H2C
   already covers? Without this, the harness risks producing redundant or contradictory
   information next to the H2C page.

2. **Crime rate normalisation.** The police API returns absolute crime counts, not
   rates. To say "low crime" vs "high crime" we need a baseline (borough or national
   average). Should the harness pull borough-level averages separately, or use a
   percentile approach across the candidate listings themselves?

3. **Coverage gaps for Scotland and Wales.** EA flood data, GIAS schools, and TfL PTAL
   all have England-only or London-only coverage. For buyers in Scotland (e.g. Edinburgh)
   or Wales (e.g. Cardiff), several enrichment categories would return warnings.
   Is this acceptable, or should the feature be blocked in the CLI until UK-wide
   coverage is achievable?

4. **Buyer permission for enrichment API calls.** Some buyers may not want their
   search data (postcode + timing) sent to multiple third-party APIs. Should the CLI
   ask explicit permission before running enrichment, or is a consent notice in the
   onboarding flow sufficient?

5. **Schools relevance gating.** The plan gates school fetching on buyer preferences.
   But buyers sometimes care about schools without mentioning it (resale value, future
   family plans). Should the tool always fetch schools and let the buyer filter, or
   should it require explicit opt-in?

6. **Data staleness.** Ofsted re-inspects schools every few years. Crime data is 2–4
   months behind. Flood zone maps update infrequently. Should the harness expose
   `retrieved_date` prominently in the UI so buyers understand they may be seeing
   slightly stale data, and if so, how prominently?

7. **Rate limits and costs.** Most APIs here are free but rate-limited. With 200
   candidate listings, we'd be making 200 × 5 = 1,000 API calls per search. Should
   enrichment be lazy (only for the final top-5) or eager (all candidates before
   ranking so ranking can use school/flood data)? Eager enrichment is better for
   ranking quality but expensive in API calls.
