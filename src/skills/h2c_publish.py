from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import html
import urllib.request

from src.models.schemas import Listing
from src.skills.h2c_publish_validation import validate_h2c_publish_listings
from src.skills.photo_verification import listing_with_photo_verification, verify_listing_photos


RenderVerifier = Callable[[str, list[Listing]], int]


@dataclass(frozen=True)
class H2CPublishResult:
    status: str
    comparison_id: str | None = None
    overview_url: str | None = None
    photos_url: str | None = None
    listings_published: int = 0
    photos_submitted: int = 0
    photos_rendered: int | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_response: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "comparison_id": self.comparison_id,
            "overview_url": self.overview_url,
            "photos_url": self.photos_url,
            "listings_published": self.listings_published,
            "photos_submitted": self.photos_submitted,
            "photos_rendered": self.photos_rendered,
            "warnings": self.warnings,
            "errors": self.errors,
            "raw_response": self.raw_response,
        }


def publish_h2c_comparison(
    listings: list[Listing],
    *,
    comparison: dict[str, object] | None = None,
    connector: object | None = None,
    min_verified_photos: int = 1,
    target_verified_photos: int = 5,
    verify_rendered_photos: bool = True,
    render_verifier: RenderVerifier | None = None,
    skip_photo_http: bool = False,
) -> H2CPublishResult:
    warnings: list[str] = []
    errors: list[str] = []
    verified_listings: list[Listing] = []

    for listing in listings:
        result = verify_listing_photos(
            listing,
            min_required=min_verified_photos,
            skip_http=skip_photo_http,
        )
        warnings.extend(result.warnings)
        verified_listings.append(listing_with_photo_verification(listing, result))

    validation = validate_h2c_publish_listings(
        verified_listings,
        min_verified_photos=min_verified_photos,
        target_verified_photos=target_verified_photos,
    )
    warnings.extend(validation.warnings)
    if not validation.ok:
        return H2CPublishResult(status="validation_failed", warnings=warnings, errors=validation.errors)

    if connector is None:
        return H2CPublishResult(
            status="publish_failed",
            warnings=warnings,
            errors=["HomesToCompare connector not configured."],
        )

    try:
        published = connector.create_comparison(verified_listings, comparison=comparison)
    except Exception as exc:
        return H2CPublishResult(status="publish_failed", warnings=warnings, errors=[str(exc)])

    comparison_id = _optional_str(published.get("comparison_id"))
    overview_url = _optional_str(published.get("overview_url"))
    photos_url = _optional_str(published.get("photos_url"))
    photos_submitted = sum(len(listing.image_urls) for listing in verified_listings)
    photos_rendered: int | None = None
    status = "published"

    if verify_rendered_photos:
        verifier = render_verifier or verify_h2c_photos_page
        if photos_url is None:
            status = "published_but_failed_verification"
            errors.append("H2C did not return a photos URL to verify.")
        else:
            try:
                photos_rendered = verifier(photos_url, verified_listings)
            except Exception as exc:
                status = "published_but_failed_verification"
                errors.append(f"H2C render verification failed: {exc}")
            else:
                if photos_rendered < len(verified_listings):
                    status = "published_but_failed_verification"
                    errors.append("H2C photos page rendered no submitted property image for every listing.")

    raw_response = published.get("raw_response")
    return H2CPublishResult(
        status=status,
        comparison_id=comparison_id,
        overview_url=overview_url,
        photos_url=photos_url,
        listings_published=len(verified_listings),
        photos_submitted=photos_submitted,
        photos_rendered=photos_rendered,
        warnings=warnings,
        errors=errors,
        raw_response=raw_response if isinstance(raw_response, dict) else {},
    )


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def verify_h2c_photos_page(photos_url: str, listings: list[Listing]) -> int:
    request = urllib.request.Request(
        photos_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8", errors="replace")
    normalized_body = html.unescape(body)
    rendered = 0
    for listing in listings:
        if any(url and url in normalized_body for url in listing.image_urls):
            rendered += 1
    return rendered
