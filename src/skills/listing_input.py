from __future__ import annotations

import re
from collections.abc import Iterable

from src.models.schemas import AreaData, AreaEvidence, Listing, PropertyDecisionDetails, SourcedValue


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
        area_data=_coerce_area_data(data.get("area_data"), listing_id=str(data.get("id", ""))),
        image_urls=_coerce_image_urls(data.get("image_urls")),
        decision_details=_coerce_decision_details(data.get("decision_details")),
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


def _coerce_image_urls(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        url = value.get("url")
        return [url.strip()] if isinstance(url, str) and url.strip() else []
    if isinstance(value, Iterable):
        urls: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                urls.append(item.strip())
            elif isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url.strip():
                    urls.append(url.strip())
            elif item not in (None, ""):
                urls.append(str(item))
        return urls
    return [str(value)]


def _coerce_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def _coerce_area_data(value: object, listing_id: str) -> AreaData | None:
    if not isinstance(value, dict):
        return None
    evidence_items: list[AreaEvidence] = []
    raw_evidence = value.get("evidence")
    if isinstance(raw_evidence, Iterable) and not isinstance(raw_evidence, (str, bytes, dict)):
        for item in raw_evidence:
            if not isinstance(item, dict):
                continue
            evidence_items.append(
                AreaEvidence(
                    category=str(item.get("category", "unknown")),
                    summary=str(item.get("summary", "")),
                    source_name=str(item.get("source_name", "unknown")),
                    source=str(item.get("source", "missing")),
                    retrieved_at=str(item.get("retrieved_at", "")),
                    jurisdiction=None if item.get("jurisdiction") is None else str(item.get("jurisdiction")),
                    confidence=None if item.get("confidence") is None else str(item.get("confidence")),
                    details=_coerce_dict(item.get("details")),
                    warnings=_coerce_string_list(item.get("warnings")),
                )
            )
    warnings = _coerce_string_list(value.get("warnings"))
    return AreaData(listing_id=listing_id, evidence=evidence_items, warnings=warnings)


def _coerce_decision_details(value: object) -> PropertyDecisionDetails | None:
    if not isinstance(value, dict):
        return None
    return PropertyDecisionDetails(
        tenure=_coerce_sourced_value(value.get("tenure")),
        lease_years_remaining=_coerce_sourced_value(value.get("lease_years_remaining")),
        service_charge_annual=_coerce_sourced_value(value.get("service_charge_annual")),
        ground_rent_annual=_coerce_sourced_value(value.get("ground_rent_annual")),
        council_tax_band=_coerce_sourced_value(value.get("council_tax_band")),
        epc_rating=_coerce_sourced_value(value.get("epc_rating")),
        chain_status=_coerce_sourced_value(value.get("chain_status")),
        parking_details=_coerce_sourced_value(value.get("parking_details")),
        outdoor_space=_coerce_sourced_value(value.get("outdoor_space")),
        condition_summary=_coerce_sourced_value(value.get("condition_summary")),
        floor_area_sqft=_coerce_sourced_value(value.get("floor_area_sqft")),
        price_per_sqft=_coerce_sourced_value(value.get("price_per_sqft")),
        flood_risk=_coerce_sourced_value(value.get("flood_risk")),
        broadband=_coerce_sourced_value(value.get("broadband")),
        notes=_coerce_string_list(value.get("notes")),
    )


def _coerce_sourced_value(value: object) -> SourcedValue | None:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        return SourcedValue(
            value=value.get("value"),
            source=str(value.get("source", "missing")),
            provider=None if value.get("provider") is None else str(value.get("provider")),
            retrieved_at=None if value.get("retrieved_at") is None else str(value.get("retrieved_at")),
            confidence=None if value.get("confidence") is None else str(value.get("confidence")),
            warnings=_coerce_string_list(value.get("warnings")),
        )
    return SourcedValue(value=value, source="listing_provided")
