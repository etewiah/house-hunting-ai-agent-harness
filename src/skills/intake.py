from __future__ import annotations

import re
from src.models.schemas import BuyerProfile


def _extract_budget(text: str, default: int = 700_000) -> int:
    match = re.search(r"[£$]?\s?(\d{3,4})\s?k", text.lower())
    if match:
        return int(match.group(1)) * 1000
    return default


def _extract_bedrooms(text: str, default: int = 3) -> int:
    match = re.search(r"(\d)\s*[- ]?bed", text.lower())
    if match:
        return int(match.group(1))
    return default


def _extract_commute(text: str) -> int | None:
    match = re.search(r"(\d{2,3})\s*minutes?", text.lower())
    if match:
        return int(match.group(1))
    return None


def parse_buyer_brief(text: str) -> BuyerProfile:
    lowered = text.lower()
    must_haves: list[str] = []
    nice_to_haves: list[str] = []

    for feature in ["garden", "walkable", "quiet", "parking", "schools"]:
        if feature in lowered:
            must_haves.append(feature)

    for feature in ["period", "renovated", "station", "park", "office"]:
        if feature in lowered:
            nice_to_haves.append(feature)

    location_query = "unknown"
    if "king" in lowered and "cross" in lowered:
        location_query = "King's Cross commute"

    return BuyerProfile(
        location_query=location_query,
        max_budget=_extract_budget(text),
        min_bedrooms=_extract_bedrooms(text),
        max_commute_minutes=_extract_commute(text),
        must_haves=must_haves,
        nice_to_haves=nice_to_haves,
        quiet_street_required="quiet" in lowered,
    )
