from __future__ import annotations

import os

from src.models.schemas import BuyerProfile, RankedListing
from src.skills.intake import LlmAdapter

_EXPLAIN_PROMPT = """\
Buyer is looking for: {profile_summary}

Listing: {title}, {location}
Price: £{price:,} | {bedrooms} bed | {bathrooms} bath | commute {commute}
Features: {features}
Match score: {score}/100
Requirements met: {matched}
Requirements missed: {missed}{warnings_line}

Write 2-3 sentences explaining to this buyer whether this listing is worth viewing and why.
Be specific — use the actual numbers. Be honest about misses. Do not give legal, mortgage,
survey, inspection, or negotiation advice."""


def _profile_summary(profile: BuyerProfile) -> str:
    parts = [f"{profile.min_bedrooms}+ bed", f"budget £{profile.max_budget:,}"]
    if profile.location_query != "unknown":
        parts.append(f"near {profile.location_query}")
    if profile.max_commute_minutes:
        parts.append(f"max {profile.max_commute_minutes} min commute")
    if profile.must_haves:
        parts.append(f"needs: {', '.join(profile.must_haves)}")
    return ", ".join(parts)


def explain_ranked_listing(
    item: RankedListing,
    profile: BuyerProfile | None = None,
    llm: LlmAdapter | None = None,
) -> str:
    if llm is not None and profile is not None:
        return _explain_with_llm(item, profile, llm)
    return _explain_with_template(item)


def _explain_with_template(item: RankedListing) -> str:
    listing = item.listing
    parts = [
        f"{listing.title} scored {item.score:.0f}/100.",
        f"Matched: {', '.join(item.matched) if item.matched else 'none'}.",
        f"Missed: {', '.join(item.missed) if item.missed else 'none'}.",
    ]
    if item.warnings:
        parts.append(f"Warnings: {', '.join(item.warnings)}.")
    commute_source = "estimated" if listing.external_refs.get("commute_estimation") else "listing_provided"
    parts.append(
        "Sources: price, bedroom count, and features are listing_provided unless marked missing; "
        f"commute is {commute_source} unless marked missing."
    )
    return " ".join(parts)


def _explain_with_llm(item: RankedListing, profile: BuyerProfile, llm: LlmAdapter) -> str:
    listing = item.listing
    commute = "unknown" if listing.commute_minutes is None else f"{listing.commute_minutes} min"
    warnings_line = (
        f"\nWarnings: {', '.join(item.warnings)}" if item.warnings else ""
    )
    prompt = _EXPLAIN_PROMPT.format(
        profile_summary=_profile_summary(profile),
        title=listing.title,
        location=listing.location,
        price=listing.price,
        bedrooms=listing.bedrooms,
        bathrooms=listing.bathrooms,
        commute=commute,
        features=", ".join(listing.features) if listing.features else "none listed",
        score=item.score,
        matched=", ".join(item.matched) if item.matched else "none",
        missed=", ".join(item.missed) if item.missed else "none",
        warnings_line=warnings_line,
    )
    return llm.generate(
        prompt,
        model=os.getenv("BUYER_AGENT_EXPLAIN_MODEL", "claude-haiku-4-5-20251001"),
    )
