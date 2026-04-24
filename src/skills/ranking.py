from __future__ import annotations

import re

from src.models.schemas import BuyerProfile, Listing, RankedListing


def rank_listing(profile: BuyerProfile, listing: Listing) -> RankedListing:
    score = 0.0
    matched: list[str] = []
    missed: list[str] = []
    warnings: list[str] = []
    breakdown: dict[str, object] = {
        "budget": {"points": 0, "status": "missing", "source": "listing_provided"},
        "bedrooms": {"points": 0, "status": "missing", "source": "listing_provided"},
        "commute": {"points": 0, "status": "not_requested", "source": "missing"},
        "must_haves": [],
        "nice_to_haves": [],
        "penalties": [],
    }

    if listing.price <= profile.max_budget:
        score += 30
        matched.append("within budget")
        breakdown["budget"] = {
            "points": 30,
            "status": "matched",
            "listing_price": listing.price,
            "max_budget": profile.max_budget,
            "source": "listing_provided",
        }
    else:
        missed.append("over budget")
        score -= 20
        breakdown["budget"] = {
            "points": -20,
            "status": "missed",
            "listing_price": listing.price,
            "max_budget": profile.max_budget,
            "source": "listing_provided",
        }
        breakdown["penalties"].append("price exceeds buyer budget")

    if listing.bedrooms >= profile.min_bedrooms:
        score += 20
        matched.append("bedroom requirement")
        breakdown["bedrooms"] = {
            "points": 20,
            "status": "matched",
            "listing_bedrooms": listing.bedrooms,
            "min_bedrooms": profile.min_bedrooms,
            "source": "listing_provided",
        }
    else:
        missed.append("too few bedrooms")
        breakdown["bedrooms"] = {
            "points": 0,
            "status": "missed",
            "listing_bedrooms": listing.bedrooms,
            "min_bedrooms": profile.min_bedrooms,
            "source": "listing_provided",
        }

    if profile.max_commute_minutes is not None:
        commute_estimation = listing.external_refs.get("commute_estimation") if listing.external_refs else None
        commute_source = "estimated" if commute_estimation is not None else "listing_provided"
        if listing.commute_minutes is None:
            warnings.append("commute time missing")
            breakdown["commute"] = {
                "points": 0,
                "status": "missing",
                "listing_commute_minutes": None,
                "max_commute_minutes": profile.max_commute_minutes,
                "source": "missing",
            }
        elif listing.commute_minutes <= profile.max_commute_minutes:
            score += 20
            matched.append("commute requirement")
            if commute_estimation is not None:
                warnings.append("commute time estimated")
            breakdown["commute"] = {
                "points": 20,
                "status": "matched",
                "listing_commute_minutes": listing.commute_minutes,
                "max_commute_minutes": profile.max_commute_minutes,
                "source": commute_source,
            }
        else:
            missed.append("commute too long")
            if commute_estimation is not None:
                warnings.append("commute time estimated")
            breakdown["commute"] = {
                "points": 0,
                "status": "missed",
                "listing_commute_minutes": listing.commute_minutes,
                "max_commute_minutes": profile.max_commute_minutes,
                "source": commute_source,
            }

    for feature in profile.must_haves:
        if _has_feature(listing, feature):
            score += 8
            matched.append(feature)
            breakdown["must_haves"].append(
                {"feature": feature, "points": 8, "status": "matched", "source": "listing_provided"}
            )
        else:
            missed.append(feature)
            breakdown["must_haves"].append(
                {"feature": feature, "points": 0, "status": "missed", "source": "missing"}
            )

    for feature in profile.nice_to_haves:
        if _has_feature(listing, feature):
            score += 3
            matched.append(feature)
            breakdown["nice_to_haves"].append(
                {"feature": feature, "points": 3, "status": "matched", "source": "listing_provided"}
            )

    return RankedListing(
        listing=listing,
        score=max(0, score),
        matched=matched,
        missed=missed,
        warnings=warnings,
        score_breakdown=breakdown,
    )


def rank_listings(profile: BuyerProfile, listings: list[Listing]) -> list[RankedListing]:
    return sorted(
        (rank_listing(profile, listing) for listing in listings),
        key=lambda item: item.score,
        reverse=True,
    )


def _has_feature(listing: Listing, feature: str) -> bool:
    feature_pattern = re.compile(r"\b" + re.escape(feature.lower()) + r"\b")
    return any(feature_pattern.search(candidate.lower()) for candidate in listing.features)
