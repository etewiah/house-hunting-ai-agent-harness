from __future__ import annotations

import json
import os
import re
from typing import Protocol
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


class LlmAdapter(Protocol):
    def generate(self, prompt: str, model: str) -> str: ...


_INTAKE_PROMPT = """Extract a buyer profile from this house-hunting brief.
Return only JSON with keys: location_query, max_budget, min_bedrooms,
max_commute_minutes, must_haves, nice_to_haves, quiet_street_required.

Brief:
{brief}
"""


def parse_buyer_brief(text: str, llm: LlmAdapter | None = None) -> BuyerProfile:
    if llm is not None:
        return _parse_with_llm(text, llm)
    return _parse_with_regex(text)


def _parse_with_llm(text: str, llm: LlmAdapter) -> BuyerProfile:
    raw = llm.generate(
        _INTAKE_PROMPT.format(brief=text),
        model=os.getenv("BUYER_AGENT_INTAKE_MODEL", "claude-haiku-4-5"),
    )
    parsed = json.loads(raw.strip())
    return BuyerProfile(
        location_query=parsed.get("location_query", "unknown"),
        max_budget=int(parsed.get("max_budget") or _extract_budget(text)),
        min_bedrooms=int(parsed.get("min_bedrooms") or _extract_bedrooms(text)),
        max_commute_minutes=parsed.get("max_commute_minutes") or _extract_commute(text),
        must_haves=list(parsed.get("must_haves") or []),
        nice_to_haves=list(parsed.get("nice_to_haves") or []),
        quiet_street_required=bool(parsed.get("quiet_street_required", False)),
    )


def _parse_with_regex(text: str) -> BuyerProfile:
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
