from __future__ import annotations

from src.models.schemas import Listing


def listing_from_dict(data: dict[str, object]) -> Listing:
    return Listing(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        price=int(data.get("price", 0) or 0),
        bedrooms=int(data.get("bedrooms", 0) or 0),
        bathrooms=int(data.get("bathrooms", 0) or 0),
        location=str(data.get("location", "")),
        commute_minutes=_coerce_optional_int(data.get("commute_minutes")),
        features=[str(item) for item in list(data.get("features") or [])],
        description=str(data.get("description", "")),
        source_url=str(data.get("source_url", "")),
        image_urls=[str(item) for item in list(data.get("image_urls") or [])],
        external_refs=dict(data.get("external_refs") or {}),
    )


def _coerce_optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
