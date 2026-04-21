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
    match = re.search(r"(\d{2,3})\s*min", text.lower())
    if match:
        return int(match.group(1))
    return None


def _extract_location(text: str) -> str:
    # Match "near X", "in X", "of X", "to X" where X starts with a capital letter
    match = re.search(
        r"(?:near|in|of|to)\s+([A-Z][A-Za-z\s']+?)(?:\s*,|\s+(?:budget|with|and|for|near|max|need|\d)|\s*$)",
        text,
    )
    if match:
        return match.group(1).strip()
    # Legacy fallback
    lowered = text.lower()
    if "king" in lowered and "cross" in lowered:
        return "King's Cross"
    return "unknown"


_MUST_HAVE_SYNONYMS: dict[str, list[str]] = {
    "garden": ["garden", "outdoor space", "rear garden", "private garden"],
    "walkable": ["walkable", "walking distance", "walk to"],
    "quiet": ["quiet", "peaceful", "no through road", "low traffic"],
    "parking": ["parking", "off-street", "driveway", "garage"],
    "schools": ["school", "schools", "ofsted", "catchment"],
}

_NICE_TO_HAVE_SYNONYMS: dict[str, list[str]] = {
    "period": ["period", "victorian", "edwardian", "georgian"],
    "renovated": ["renovated", "refurbished", "modernised", "updated"],
    "station": ["station", "tube", "metro", "tram", "transport links"],
    "park": ["park", "green space", "common", "recreation ground"],
    "office": ["office", "home office", "study", "work from home"],
}

_REQUIRED_HINTS = ["need", "must", "essential", "require", "required"]
_PREFERRED_HINTS = ["prefer", "preferred", "ideally", "nice to have", "would like"]


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


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"```(?:json)?\s*\n?", "", text).rstrip("`").strip()
    return json.loads(text)


def _parse_with_llm(text: str, llm: LlmAdapter) -> BuyerProfile:
    raw = llm.generate(
        _INTAKE_PROMPT.format(brief=text),
        model=os.getenv("BUYER_AGENT_INTAKE_MODEL", "claude-haiku-4-5-20251001"),
    )
    parsed = _extract_json(raw)
    return BuyerProfile(
        location_query=parsed.get("location_query", "unknown"),
        max_budget=int(parsed.get("max_budget") or _extract_budget(text)),
        min_bedrooms=int(parsed.get("min_bedrooms") or _extract_bedrooms(text)),
        max_commute_minutes=parsed.get("max_commute_minutes") or _extract_commute(text),
        must_haves=list(parsed.get("must_haves") or []),
        nice_to_haves=list(parsed.get("nice_to_haves") or []),
        quiet_street_required=bool(parsed.get("quiet_street_required", False)),
    )


def _phrase_pattern(phrase: str) -> str:
    return r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\b"


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(_phrase_pattern(phrase), text) is not None


def _mentions_any(text: str, phrases: list[str]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _feature_mentioned(text: str, synonyms: list[str]) -> bool:
    return any(_contains_phrase(text, synonym) for synonym in synonyms)


def _preferred_feature(text: str, synonyms: list[str]) -> bool:
    for synonym in synonyms:
        pattern = _phrase_pattern(synonym)
        if re.search(rf"(?:{'|'.join(map(re.escape, _PREFERRED_HINTS))})[^,.]*{pattern}", text):
            return True
        if re.search(rf"{pattern}[^,.]*(?:{'|'.join(map(re.escape, _PREFERRED_HINTS))})", text):
            return True
    return False


def _required_feature(text: str, synonyms: list[str]) -> bool:
    for synonym in synonyms:
        pattern = _phrase_pattern(synonym)
        if re.search(rf"(?:{'|'.join(map(re.escape, _REQUIRED_HINTS))})[^,.]*{pattern}", text):
            return True
        if re.search(rf"{pattern}[^,.]*(?:{'|'.join(map(re.escape, _REQUIRED_HINTS))})", text):
            return True
    return False


def _parse_with_regex(text: str) -> BuyerProfile:
    lowered = text.lower()
    must_haves: list[str] = []
    nice_to_haves: list[str] = []

    for feature, synonyms in _MUST_HAVE_SYNONYMS.items():
        if not _feature_mentioned(lowered, synonyms):
            continue
        if _preferred_feature(lowered, synonyms) and not _required_feature(lowered, synonyms):
            nice_to_haves.append(feature)
        else:
            must_haves.append(feature)

    for feature, synonyms in _NICE_TO_HAVE_SYNONYMS.items():
        if _feature_mentioned(lowered, synonyms):
            nice_to_haves.append(feature)

    quiet_street_required = _required_feature(lowered, _MUST_HAVE_SYNONYMS["quiet"]) or (
        _feature_mentioned(lowered, _MUST_HAVE_SYNONYMS["quiet"]) and not _preferred_feature(lowered, _MUST_HAVE_SYNONYMS["quiet"])
    )

    return BuyerProfile(
        location_query=_extract_location(text),
        max_budget=_extract_budget(text),
        min_bedrooms=_extract_bedrooms(text),
        max_commute_minutes=_extract_commute(text),
        must_haves=must_haves,
        nice_to_haves=nice_to_haves,
        quiet_street_required=quiet_street_required,
    )
