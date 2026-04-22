from __future__ import annotations

from src.models.schemas import Listing


def compare_homes(listings: list[Listing]) -> str:
    if not listings:
        return "No listings selected for comparison."

    lines = ["# Home Comparison", ""]
    for listing in listings:
        commute = "missing" if listing.commute_minutes is None else f"{listing.commute_minutes} mins"
        if listing.external_refs.get("commute_estimation"):
            commute = f"{commute} (estimated)"
        lines.append(
            f"- {listing.title}: £{listing.price:,}, {listing.bedrooms} beds, "
            f"{listing.bathrooms} baths, commute {commute}, features: {', '.join(listing.features)}"
        )
    lines.append("")
    lines.append("Boundary: this is a comparison aid, not legal, mortgage, survey, or inspection advice.")
    return "\n".join(lines)
