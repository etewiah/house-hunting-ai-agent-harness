from __future__ import annotations

from src.models.schemas import BuyerProfile, Listing, RankedListing


def rank_listing(profile: BuyerProfile, listing: Listing) -> RankedListing:
    score = 0.0
    matched: list[str] = []
    missed: list[str] = []
    warnings: list[str] = []

    if listing.price <= profile.max_budget:
        score += 30
        matched.append("within budget")
    else:
        missed.append("over budget")
        score -= 20

    if listing.bedrooms >= profile.min_bedrooms:
        score += 20
        matched.append("bedroom requirement")
    else:
        missed.append("too few bedrooms")

    if profile.max_commute_minutes is not None:
        if listing.commute_minutes is None:
            warnings.append("commute time missing")
        elif listing.commute_minutes <= profile.max_commute_minutes:
            score += 20
            matched.append("commute requirement")
        else:
            missed.append("commute too long")

    for feature in profile.must_haves:
        if feature in listing.features:
            score += 8
            matched.append(feature)
        else:
            missed.append(feature)

    for feature in profile.nice_to_haves:
        if feature in listing.features:
            score += 3
            matched.append(feature)

    return RankedListing(
        listing=listing,
        score=max(0, score),
        matched=matched,
        missed=missed,
        warnings=warnings,
    )


def rank_listings(profile: BuyerProfile, listings: list[Listing]) -> list[RankedListing]:
    return sorted(
        (rank_listing(profile, listing) for listing in listings),
        key=lambda item: item.score,
        reverse=True,
    )
