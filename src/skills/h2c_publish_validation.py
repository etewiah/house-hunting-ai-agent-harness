from __future__ import annotations

from dataclasses import dataclass, field

from src.models.schemas import Listing


@dataclass(frozen=True)
class H2CPublishValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    photo_counts: dict[str, int] = field(default_factory=dict)


def validate_h2c_publish_listings(
    listings: list[Listing],
    *,
    min_verified_photos: int = 1,
    target_verified_photos: int = 5,
) -> H2CPublishValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    photo_counts: dict[str, int] = {}

    if len(listings) < 2:
        errors.append("At least two listings are required to create an H2C comparison.")

    for index, listing in enumerate(listings, 1):
        label = listing.title or listing.id or f"listing {index}"
        if not listing.source_url:
            errors.append(f"{label}: source_url is required.")
        if listing.price <= 0:
            errors.append(f"{label}: price is required.")
        if not listing.title:
            errors.append(f"{label}: title is required.")
        if not listing.location:
            errors.append(f"{label}: location is required.")

        verified_count = _verified_photo_count(listing)
        photo_counts[listing.id or label] = verified_count
        if verified_count < min_verified_photos:
            errors.append(
                f"{label}: {verified_count} verified photo(s); "
                f"{min_verified_photos} required for H2C publishing."
            )
        elif verified_count < target_verified_photos:
            warnings.append(
                f"{label}: {verified_count} verified photo(s); target is {target_verified_photos}."
            )

        if listing.bathrooms <= 0:
            warnings.append(f"{label}: bathroom count is missing.")
        if listing.decision_details is None:
            warnings.append(f"{label}: decision details are missing.")

    return H2CPublishValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        photo_counts=photo_counts,
    )


def _verified_photo_count(listing: Listing) -> int:
    extraction = listing.external_refs.get("photo_extraction")
    if isinstance(extraction, dict) and extraction.get("status") == "verified":
        count = extraction.get("verified_photo_count")
        if isinstance(count, int):
            return count
        photos = extraction.get("photos")
        if isinstance(photos, list):
            return len(photos)
    return 0
