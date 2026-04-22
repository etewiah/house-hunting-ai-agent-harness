from __future__ import annotations

import re
from collections.abc import Iterable

from src.models.schemas import Listing


def listing_from_dict(data: dict[str, object]) -> Listing:
    return Listing(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        price=_coerce_int(data.get("price")),
        bedrooms=_coerce_int(data.get("bedrooms")),
        bathrooms=_coerce_int(data.get("bathrooms")),
        location=str(data.get("location", "")),
        commute_minutes=_coerce_optional_int(data.get("commute_minutes")),
        features=_coerce_string_list(data.get("features")),
        description=str(data.get("description", "")),
        source_url=str(data.get("source_url", "")),
        image_urls=_coerce_string_list(data.get("image_urls")),
        external_refs=_coerce_dict(data.get("external_refs")),
    )


def _coerce_optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return _coerce_int(value)


def _coerce_int(value: object) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return 0
        digits = re.findall(r"\d+", cleaned.replace(",", ""))
        if digits:
            return int("".join(digits[:1]))
    raise ValueError(f"Cannot coerce value to int: {value!r}")


def _coerce_string_list(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


def _coerce_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}
