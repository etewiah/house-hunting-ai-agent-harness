from __future__ import annotations

from src.models.schemas import RankedListing


def explain_ranked_listing(item: RankedListing) -> str:
    listing = item.listing
    parts = [
        f"{listing.title} scored {item.score:.0f}/100.",
        f"Matched: {', '.join(item.matched) if item.matched else 'none'}.",
        f"Missed: {', '.join(item.missed) if item.missed else 'none'}.",
    ]
    if item.warnings:
        parts.append(f"Warnings: {', '.join(item.warnings)}.")
    parts.append("Sources: price, bedroom count, features, and commute are listing_provided unless marked missing.")
    return " ".join(parts)
