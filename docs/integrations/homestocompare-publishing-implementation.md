# HomesToCompare Publishing Implementation Plan

## Current State

The project already has useful pieces:

- `Listing.image_urls` exists in `src/models/schemas.py`.
- Browser extraction can capture `image_urls` in `.pi/extensions/house-hunt-browser/`.
- Browser-assisted workflows can rank listings without a configured provider.
- `HomesToCompareConnector.create_comparison(...)` exists.

But the current implementation is not the right publishing contract for the workflow the
user expects.

Problems to fix:

- `HomesToCompareConnector` requires `H2C_SERVICE_KEY`.
- It posts to `/api/house-hunt/create-comparison`, which is not the public comparison
  flow used by the browser-created comparison.
- `H2C_BASE_URL` should not be required because the default should be
  `https://homestocompare.com`.
- Publishing does not require verified photos.
- Publishing does not verify that H2C rendered submitted photos.
- The browser-house-hunt skill treats photos as optional diagnostics instead of a
  required part of an H2C comparison.
- The payload does not explicitly guard against currency inference bugs.

## Proposed Modules

### `src/skills/photo_verification.py`

Responsible for verifying candidate image URLs.

Suggested public API:

```python
@dataclass(frozen=True)
class VerifiedPhoto:
    url: str
    observed_in: str
    status_code: int | None = None
    content_type: str | None = None
    natural_width: int | None = None
    natural_height: int | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PhotoVerificationResult:
    listing_id: str
    status: str
    verified: list[VerifiedPhoto]
    rejected: list[dict[str, object]]
    warnings: list[str]


def verify_listing_photos(listing: Listing, *, min_required: int = 1) -> PhotoVerificationResult:
    ...
```

Implementation notes:

- Use `urllib.request` for Python-side HTTP verification.
- Treat non-image content types as rejected.
- Follow redirects but reject final HTML responses.
- Deduplicate URLs before verification.
- Keep timeout short and collect warnings instead of hanging the workflow.
- Do not mutate `Listing`; return a result and let the caller create an updated listing
  with `external_refs.photo_extraction`.

### `src/skills/h2c_publish_validation.py`

Responsible for deciding whether selected listings are publishable to H2C.

Suggested public API:

```python
@dataclass(frozen=True)
class H2CPublishValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]
    photo_counts: dict[str, int]


def validate_h2c_publish_listings(
    listings: list[Listing],
    *,
    min_verified_photos: int = 1,
    target_verified_photos: int = 5,
) -> H2CPublishValidationResult:
    ...
```

Hard failures:

- no listings
- fewer than two listings for a comparison
- missing source URL
- missing price
- missing title
- missing location
- no verified photos
- photo metadata says verification failed

Warnings:

- below target photo count
- missing EPC
- missing tenure
- missing rent/yield for investment briefs
- missing floor area

### `src/connectors/homestocompare_mapper.py`

Responsible for translating `Listing` into H2C's public comparison payload shape.

Suggested public API:

```python
def listing_to_h2c_property_data(listing: Listing) -> dict[str, object]:
    ...


def build_h2c_public_comparison_payload(
    listings: list[Listing],
    *,
    comparison: dict[str, object] | None = None,
) -> dict[str, object]:
    ...
```

Mapping requirements:

- Use `source_url` as the canonical URL.
- Emit both `price_float` and `price_string`.
- Emit explicit `currency: "GBP"` for UK listings.
- Ensure `price_string` starts with `£` for UK listings.
- Emit image data in the exact shape H2C accepts.
- Preserve original listing URLs and portal names.
- Include ranked score and recommendation metadata when available.
- Include extraction diagnostics under a namespaced field such as
  `house_hunt_agent`.

### `src/connectors/homestocompare_public_connector.py`

Responsible for the public, no-service-key publishing flow.

Suggested public API:

```python
class HomesToComparePublicConnector:
    def __init__(self, base_url: str = "https://homestocompare.com") -> None:
        ...

    def create_comparison(self, listings: list[Listing], comparison: dict[str, object] | None = None) -> dict[str, object]:
        ...
```

Behavior:

- Default `base_url` to `https://homestocompare.com`.
- Do not require `H2C_SERVICE_KEY`.
- Post to the stable public comparison endpoint.
- Return normalized URLs for overview and photos pages.
- Preserve raw response in diagnostics.
- Raise a clear exception when H2C returns a schema, auth, or validation error.

The existing `HomesToCompareConnector` can remain for the service-key API if it is still
useful, but it should not be the path used for browser-assisted user-facing publishing.

### `src/skills/h2c_publish.py`

Responsible for orchestration.

Suggested public API:

```python
@dataclass(frozen=True)
class H2CPublishResult:
    status: str
    comparison_id: str | None
    overview_url: str | None
    photos_url: str | None
    listings_published: int
    photos_submitted: int
    photos_rendered: int | None
    warnings: list[str]
    errors: list[str]


def publish_h2c_comparison(
    listings: list[Listing],
    *,
    comparison: dict[str, object] | None = None,
    verify_rendered_photos: bool = True,
) -> H2CPublishResult:
    ...
```

Flow:

1. Verify or reverify listing photos.
2. Validate selected listings.
3. Build H2C payload.
4. Publish to H2C.
5. Verify H2C photos page when browser automation is available.
6. Return a success result only if publish validation passes.

## Browser Extension Changes

Files:

- `.pi/extensions/house-hunt-browser/extractor-core.mjs`
- `.pi/extensions/house-hunt-browser/index.ts`
- `.pi/skills/browser-house-hunt/SKILL.md`
- `.agents/skills/browser-house-hunt/SKILL.md`

Required changes:

- Treat image extraction as required for H2C publishing.
- Track where each image URL was observed.
- Preserve rejected image candidates and reasons.
- Add a tool option such as `requireVerifiedPhotos`.
- Add a tool option such as `publishToH2C`.
- Return H2C publish diagnostics when publishing is requested.
- Update skill instructions to say H2C links must not be returned unless photos were
  verified and render-checked.

The extraction code may still return listings with no photos for ranking-only workflows.
The stricter requirement applies when the requested output is an H2C comparison.

## CLI and MCP Changes

### CLI

The standalone CLI should not pretend it can browse. For browser-assisted workflows,
the publishing path should live in the browser/Pi/Codex-assisted runner rather than the
plain `uv run house-hunt` intake flow.

Update `.pi/skills/browser-house-hunt/run_house_hunt.py` to support:

```bash
uv run --extra dev python .pi/skills/browser-house-hunt/run_house_hunt.py \
  --brief "Find an investment property in Preston" \
  --listings-file .tmp/preston-listings.json \
  --publish-h2c
```

Expected output:

```text
H2C comparison:
  Overview: https://homestocompare.com/pc/wrnkziuo/overview
  Photos:   https://homestocompare.com/pc/wrnkziuo/photos
  Photos:   18 submitted, 18 rendered
```

### MCP

Add an optional publishing surface to `src/ui/mcp_server.py`:

- `publish_h2c_comparison(listings, comparison=None)`
- or `run_house_hunt(..., publish_h2c=True)`

The response should include:

- `h2c_publish.status`
- `h2c_publish.overview_url`
- `h2c_publish.photos_url`
- `h2c_publish.photos_submitted`
- `h2c_publish.photos_rendered`
- `h2c_publish.errors`
- `h2c_publish.warnings`

## Render Verification

The best verification is browser-based:

1. Open `https://homestocompare.com/pc/{id}/photos`.
2. Collect image elements associated with submitted listing photo URLs.
3. Assert every selected listing has at least one rendered image.
4. Count rendered submitted photos with non-zero natural dimensions.

If browser automation is unavailable, Python may use HTTP verification as a weaker
fallback, but the result should say render verification was skipped.

Recommended result states:

- `published`
- `published_render_verification_skipped`
- `published_but_failed_verification`
- `validation_failed`
- `publish_failed`

## Tests

### Python unit tests

Add tests under `evals/tests/` for:

- `photo_verification` accepts real image content types.
- `photo_verification` rejects HTML, 404, and duplicate URLs.
- `h2c_publish_validation` fails when photos are missing.
- `h2c_publish_validation` warns when photo count is below target.
- `homestocompare_mapper` emits GBP currency and `£` price strings.
- `homestocompare_mapper` includes every verified image URL.
- `homestocompare_public_connector` posts without a service key.

### Extension tests

Add tests under `.pi/extensions/house-hunt-browser/test/` for:

- Rightmove fixture image extraction with observed URLs.
- OnTheMarket fixture image extraction with observed URLs.
- rejection of guessed URL templates.
- diagnostics for missing or invalid photos.

### End-to-end mocked test

Add a mocked H2C publish test:

1. Load two fixture listings with verified photos.
2. Publish through a fake H2C endpoint.
3. Return a fake comparison ID.
4. Verify fake photos page image dimensions.
5. Assert final status is `published`.

Add a failing variant where the photos page renders zero submitted photos and assert the
status is `published_but_failed_verification`.

## Implementation Sequence

1. Add photo verification result types and validation helpers.
2. Add H2C mapper tests and mapper implementation.
3. Add public H2C connector with mocked tests.
4. Add publish orchestration.
5. Wire the browser-assisted runner to `--publish-h2c`.
6. Add MCP publishing surface if needed.
7. Update browser/Pi extension extraction diagnostics.
8. Add render verification.
9. Update project-local skills and docs.
10. Run:

```bash
uv run --extra dev pytest
cd .pi/extensions/house-hunt-browser
npm test
npm run validate-fixtures
```

## Operational Rules For Agents

When a user asks for a HomesToCompare comparison link:

- collect actual listing pages first
- extract all available listing details
- extract image URLs only from observed data
- verify image URLs
- refuse to publish if photos are missing or unverified
- publish a complete H2C payload
- verify the H2C photos page
- return the H2C URL only when verification passes or clearly label partial failure

Agents must not:

- invent image URLs
- silently drop photos
- report a comparison as complete when H2C rendered no property photos
- rely on `H2C_SERVICE_KEY`
- require `H2C_BASE_URL` for the production default
- leave currency inference to chance for UK listings
