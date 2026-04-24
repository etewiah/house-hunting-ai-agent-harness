# 07 - Verified H2C Comparison Publishing

## Problem

The browser-assisted house hunt can find and rank real listings, but the handoff to
HomesToCompare is not yet reliable enough to treat as a finished user workflow.

The failure mode is severe:

- the agent can find the right property pages
- the harness can rank the right listings
- H2C can create a comparison shell
- but the comparison can be missing photos, use stale photos, or receive incomplete
  property data

That creates a misleading result. The user asked for a HomesToCompare comparison with
all details. A comparison without verified listing photos is not complete.

## Principle

The house-hunting harness owns web discovery and extraction.

HomesToCompare should not be expected to discover the right portal URLs, scrape portal
pages, infer missing photo URLs, or guess data that the agent failed to provide. The
harness has the browser/search tools and should pass H2C a complete, verified payload.

H2C still has responsibilities:

- validate the received payload
- reject or warn about bad data
- persist complete property records and photos
- render the comparison accurately
- avoid reusing stale no-photo records when fresh data is provided

But the harness must do the discovery work.

## Goals

- Create H2C comparisons from browser-assisted house-hunt results without requiring an
  `H2C_SERVICE_KEY`.
- Default H2C publishing to `https://homestocompare.com`.
- Require verified image URLs before publishing selected listings to H2C.
- Never synthesize or hallucinate image URLs.
- Preserve extraction provenance and verification diagnostics.
- Return a shareable H2C comparison URL only after the published comparison has been
  checked for rendered photos.
- Fail clearly when listing data is incomplete instead of creating a poor comparison.

## Non-goals

- Do not make H2C responsible for scraping Rightmove, Zoopla, OnTheMarket, or other
  portals on behalf of this harness.
- Do not require the core ranking workflow to have photos. Photo completeness is required
  only for H2C publishing.
- Do not add legal, mortgage, survey, inspection, or valuation advice.
- Do not move portal-specific extraction into core ranking skills. Keep it in browser
  extraction and publishing support modules.

## Target Workflow

1. Parse the buyer brief.
2. Search or browse for candidate listing pages.
3. Extract structured listing data from observed page content.
4. Extract image URLs only from observed page content, page state, JSON-LD, scripts,
   network-observed media, or DOM images.
5. Verify image URLs.
6. Normalize listings into `src.models.schemas.Listing`.
7. Rank and compare listings.
8. Select listings for H2C comparison.
9. Validate selected listings against the H2C publish contract.
10. Map selected listings into the H2C public comparison payload.
11. Publish to H2C.
12. Verify the resulting H2C photos page renders expected property images.
13. Return the H2C comparison URL and diagnostics.

## Data Contract

The existing `Listing.image_urls` field remains the canonical list of image URLs used
by downstream flows. For H2C publishing, those URLs must be verified and provenance must
be recorded in `Listing.external_refs`.

Recommended metadata shape:

```json
{
  "photo_extraction": {
    "status": "verified",
    "provider": "rightmove",
    "source_url": "https://www.rightmove.co.uk/properties/173525018",
    "extraction_methods": ["page_state", "dom_image"],
    "photo_count": 12,
    "verified_photo_count": 12,
    "verified_at": "2026-04-24T12:30:00Z",
    "photos": [
      {
        "url": "https://media.rightmove.co.uk/...",
        "observed_in": "page_state",
        "content_type": "image/jpeg",
        "status_code": 200,
        "natural_width": 656,
        "natural_height": 437
      }
    ],
    "warnings": []
  }
}
```

For H2C publishing, each selected listing should have:

- `id`
- `title`
- `price`
- `bedrooms`
- `bathrooms`
- `location`
- `description`
- `features`
- `source_url`
- `image_urls`
- `external_refs.photo_extraction.status == "verified"`
- enough verified photos to make the H2C photos page useful

Investment-specific fields should be preserved when found:

- tenure
- lease years remaining
- service charge
- ground rent
- EPC rating
- council tax band
- floor area
- rental income
- gross yield
- tenant-in-situ status
- agent name
- listing portal
- extraction timestamp

These can live in `decision_details`, `features`, and `external_refs` until a richer
investment model exists.

## Photo Verification Rules

The harness must not create image URLs by guessing known media URL patterns. A URL is
eligible only when it was observed in one of these places:

- canonical page HTML
- embedded JSON application state
- JSON-LD
- meta tags
- DOM image or source elements
- browser performance entries
- network responses seen during page load
- a documented provider API response actually fetched by the agent

Each candidate photo URL must be verified by at least one of:

- HTTP `GET` or `HEAD` returning a successful status and image content type
- browser image load with non-zero `naturalWidth` and `naturalHeight`
- a same-origin extraction result whose image dimensions were observed in the DOM

Rejected URLs should be recorded in diagnostics with a reason, for example:

- non-image content type
- HTTP 403, 404, or redirect to HTML
- browser load failure
- blocked response
- duplicate
- too small to be useful
- URL was inferred rather than observed

## Publish Validation

Before calling H2C, add a validation step for the selected comparison listings.

The validator should fail hard when:

- `source_url` is missing
- `price` is missing or zero
- `title` or `location` is empty
- `image_urls` is empty
- image URLs are not marked as verified
- a verified image URL no longer loads
- there are fewer than the configured minimum number of verified images

The validator may warn, but not fail, when:

- bathroom count is missing
- EPC is missing
- tenure is missing
- floor area is missing
- yield is estimated rather than listing-provided

The default minimum should be strict enough to prevent empty comparisons. A reasonable
starting point is:

- minimum 1 verified image per listing to publish
- target 5 or more verified images per listing when portal data supports it
- diagnostics warning below the target

## H2C Publishing Result

The publish operation should return:

```json
{
  "status": "published",
  "comparison_id": "wrnkziuo",
  "overview_url": "https://homestocompare.com/pc/wrnkziuo/overview",
  "photos_url": "https://homestocompare.com/pc/wrnkziuo/photos",
  "listings_published": 2,
  "photos_submitted": 18,
  "photos_rendered": 18,
  "warnings": []
}
```

If H2C returns an ID but the photos page does not render property images, the result
should not be reported as success. It should be:

```json
{
  "status": "published_but_failed_verification",
  "comparison_id": "xdesumyp",
  "overview_url": "https://homestocompare.com/pc/xdesumyp/overview",
  "photos_url": "https://homestocompare.com/pc/xdesumyp/photos",
  "photos_submitted": 18,
  "photos_rendered": 0,
  "warnings": ["H2C photos page rendered no submitted property images"]
}
```

## Acceptance Criteria

- Running a browser-assisted investment-property hunt can produce an H2C URL without
  requiring `H2C_SERVICE_KEY`.
- The returned H2C URL contains rendered property photos for every selected listing.
- The harness refuses to publish when selected listings have no verified photos.
- The harness never constructs photo URLs from guessed media URL templates.
- H2C payloads include explicit GBP currency data for UK listings.
- Publish diagnostics explain which fields and photos were extracted, verified, rejected,
  submitted, and rendered.
- Tests cover success, missing-photo failure, bad-photo failure, and currency mapping.

## Open Questions

- What exact public H2C endpoint should be treated as stable for comparison creation?
- Should H2C support an explicit `source_import_id` to avoid stale no-photo dedupe
  collisions?
- Should the harness publish only the top two ranked listings or allow a configurable
  shortlist size?
- Should the browser extension perform render verification, or should Python own it
  through a browser automation adapter?
- How long should verified image URLs be cached before revalidation?
