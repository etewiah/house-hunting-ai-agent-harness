from __future__ import annotations

from src.models.schemas import (
    ComparisonDimension,
    ComparisonResult,
    Listing,
    RankedListing,
    VerificationItem,
)


def build_comparison_result(
    ranked_listings: list[RankedListing],
    *,
    max_listings: int = 3,
) -> ComparisonResult:
    listings = [item.listing for item in ranked_listings[:max_listings]]
    if not listings:
        return ComparisonResult(
            listings=[],
            recommendation_listing_id=None,
            recommendation_summary="No listings selected for comparison.",
            close_call_score=0.0,
            confidence="low",
            warnings=["No listings were available to compare."],
        )

    top_ranked = ranked_listings[0]
    runner_up = ranked_listings[1] if len(ranked_listings) > 1 else None
    close_call_score = _close_call_score(top_ranked, runner_up)
    confidence = _comparison_confidence(ranked_listings[:max_listings])
    summary = _recommendation_summary(top_ranked, runner_up, close_call_score, confidence)

    return ComparisonResult(
        listings=listings,
        recommendation_listing_id=top_ranked.listing.id,
        recommendation_summary=summary,
        close_call_score=close_call_score,
        dimensions=_comparison_dimensions(ranked_listings[:max_listings]),
        trade_offs=_trade_offs(ranked_listings[:max_listings]),
        deal_breakers=_deal_breakers(ranked_listings[:max_listings]),
        verification_items=_verification_items(ranked_listings[:max_listings]),
        confidence=confidence,
        warnings=_comparison_warnings(ranked_listings[:max_listings]),
    )


def compare_ranked_homes(ranked_listings: list[RankedListing], count: int = 3) -> str:
    return render_comparison_markdown(
        build_comparison_result(ranked_listings, max_listings=count)
    )


def compare_homes(listings: list[Listing]) -> str:
    if not listings:
        return "No listings selected for comparison."

    ranked = [
        RankedListing(
            listing=listing,
            score=0,
            matched=[],
            missed=[],
            warnings=[],
        )
        for listing in listings
    ]
    return render_comparison_markdown(
        build_comparison_result(ranked, max_listings=len(listings))
    )


def render_comparison_markdown(result: ComparisonResult) -> str:
    if not result.listings:
        return "No listings selected for comparison."

    lines = [
        "# Home Comparison",
        "",
        f"Recommendation: {result.recommendation_summary}",
        f"Confidence: {result.confidence}",
        f"Close-call score: {result.close_call_score:.2f}",
        "",
        "## Side-by-side",
    ]
    for listing in result.listings:
        commute = "missing" if listing.commute_minutes is None else f"{listing.commute_minutes} mins"
        if listing.external_refs.get("commute_estimation"):
            commute = f"{commute} (estimated)"
        lines.append(
            f"- {listing.title}: £{listing.price:,}, {listing.bedrooms} beds, "
            f"{listing.bathrooms} baths, commute {commute}, features: {', '.join(listing.features)}"
        )
        if listing.area_data and listing.area_data.evidence:
            top = listing.area_data.evidence[:2]
            area_bits = [
                f"{item.category} ({item.source}): {item.summary}"
                for item in top
            ]
            lines.append(f"  area context: {' | '.join(area_bits)}")

    if result.trade_offs:
        lines.extend(["", "## Visible trade-offs"])
        lines.extend([f"- {item}" for item in result.trade_offs])

    if result.deal_breakers:
        lines.extend(["", "## Possible deal-breakers"])
        lines.extend([f"- {item}" for item in result.deal_breakers])

    if result.verification_items:
        lines.extend(["", "## What to verify next"])
        for item in result.verification_items:
            target = item.listing_id or "all listings"
            lines.append(f"- [{item.priority}] {target}: {item.question} Reason: {item.reason}")

    lines.append("")
    lines.append("Boundary: this is a comparison aid, not legal, mortgage, survey, or inspection advice.")
    return "\n".join(lines)


def _comparison_dimensions(items: list[RankedListing]) -> list[ComparisonDimension]:
    dimensions = [
        _price_dimension(items),
        _bedrooms_dimension(items),
        _commute_dimension(items),
        _evidence_dimension(items),
    ]
    return [dimension for dimension in dimensions if dimension is not None]


def _price_dimension(items: list[RankedListing]) -> ComparisonDimension | None:
    if not items:
        return None
    winner = min(items, key=lambda item: item.listing.price)
    return ComparisonDimension(
        name="price",
        winner_listing_id=winner.listing.id,
        summaries={
            item.listing.id: f"£{item.listing.price:,}"
            for item in items
        },
        source="listing_provided",
        confidence="high",
    )


def _bedrooms_dimension(items: list[RankedListing]) -> ComparisonDimension | None:
    if not items:
        return None
    winner = max(items, key=lambda item: item.listing.bedrooms)
    return ComparisonDimension(
        name="bedrooms",
        winner_listing_id=winner.listing.id,
        summaries={
            item.listing.id: f"{item.listing.bedrooms} bedrooms"
            for item in items
        },
        source="listing_provided",
        confidence="high",
    )


def _commute_dimension(items: list[RankedListing]) -> ComparisonDimension | None:
    with_commute = [item for item in items if item.listing.commute_minutes is not None]
    if not with_commute:
        return ComparisonDimension(
            name="commute",
            winner_listing_id=None,
            summaries={item.listing.id: "missing" for item in items},
            source="missing",
            confidence="low",
            warnings=["No commute times are available."],
        )
    winner = min(with_commute, key=lambda item: item.listing.commute_minutes or 10**9)
    warnings = [
        f"{item.listing.title}: commute is estimated"
        for item in with_commute
        if item.listing.external_refs.get("commute_estimation")
    ]
    return ComparisonDimension(
        name="commute",
        winner_listing_id=winner.listing.id,
        summaries={
            item.listing.id: (
                "missing"
                if item.listing.commute_minutes is None
                else f"{item.listing.commute_minutes} minutes"
            )
            for item in items
        },
        source="estimated" if warnings else "listing_provided",
        confidence="medium" if warnings else "high",
        warnings=warnings,
    )


def _evidence_dimension(items: list[RankedListing]) -> ComparisonDimension | None:
    if not items:
        return None
    winner = max(items, key=lambda item: _evidence_count(item.listing))
    return ComparisonDimension(
        name="evidence quality",
        winner_listing_id=winner.listing.id if _evidence_count(winner.listing) > 0 else None,
        summaries={
            item.listing.id: f"{_evidence_count(item.listing)} area evidence items"
            for item in items
        },
        source="inferred",
        confidence="medium",
    )


def _trade_offs(items: list[RankedListing]) -> list[str]:
    trade_offs: list[str] = []
    for item in items:
        listing = item.listing
        misses = ", ".join(item.missed) if item.missed else "no major misses"
        trade_offs.append(
            f"{listing.title}: gains {', '.join(item.matched) or 'no confirmed preferences'}; gives up {misses}."
        )
    return trade_offs


def _deal_breakers(items: list[RankedListing]) -> list[str]:
    blockers: list[str] = []
    for item in items:
        if "over budget" in item.missed:
            blockers.append(f"{item.listing.title}: over the buyer's budget.")
        if "too few bedrooms" in item.missed:
            blockers.append(f"{item.listing.title}: below the bedroom requirement.")
        if "commute too long" in item.missed:
            blockers.append(f"{item.listing.title}: commute is longer than requested.")
    return blockers


def _verification_items(items: list[RankedListing]) -> list[VerificationItem]:
    checks: list[VerificationItem] = []
    for item in items:
        listing = item.listing
        if listing.commute_minutes is None:
            checks.append(
                VerificationItem(
                    listing_id=listing.id,
                    category="commute",
                    question="Confirm realistic peak-time commute from the exact address.",
                    reason="The listing has no commute time, so the ranking cannot verify this preference.",
                    priority="high",
                    source="missing",
                )
            )
        elif listing.external_refs.get("commute_estimation"):
            checks.append(
                VerificationItem(
                    listing_id=listing.id,
                    category="commute",
                    question="Check the commute in a live maps or transport provider.",
                    reason="The current commute value is estimated, not provider-confirmed.",
                    priority="medium",
                    source="estimated",
                )
            )
        if not listing.area_data or not listing.area_data.evidence:
            checks.append(
                VerificationItem(
                    listing_id=listing.id,
                    category="area",
                    question="Collect independent area evidence before making a final decision.",
                    reason="No area evidence is attached to this listing.",
                    priority="medium",
                    source="missing",
                )
            )
        diagnostics = listing.external_refs.get("extraction_diagnostics") if listing.external_refs else None
        missing_fields = diagnostics.get("missingFields", []) if isinstance(diagnostics, dict) else []
        for field in missing_fields[:3]:
            checks.append(
                VerificationItem(
                    listing_id=listing.id,
                    category="listing-data",
                    question=f"Verify the listing field: {field}.",
                    reason="Browser extraction marked this field as missing or unconfirmed.",
                    priority="medium",
                    source="missing",
                )
            )
    return checks


def _comparison_warnings(items: list[RankedListing]) -> list[str]:
    warnings: list[str] = []
    for item in items:
        warnings.extend([f"{item.listing.title}: {warning}" for warning in item.warnings])
    return warnings


def _recommendation_summary(
    top: RankedListing,
    runner_up: RankedListing | None,
    close_call_score: float,
    confidence: str,
) -> str:
    if runner_up is None:
        return (
            f"{top.listing.title} is the only compared home. It should be treated as a "
            f"single-option review, not a true shortlist decision."
        )
    if close_call_score >= 0.85:
        return (
            f"{top.listing.title} is only narrowly ahead of {runner_up.listing.title}; "
            "verify the unresolved trade-offs before treating it as the stronger option."
        )
    return (
        f"{top.listing.title} looks stronger than {runner_up.listing.title} on the current "
        f"buyer brief, with {confidence} confidence based on available evidence."
    )


def _close_call_score(top: RankedListing, runner_up: RankedListing | None) -> float:
    if runner_up is None:
        return 0.0
    if top.score <= 0:
        return 1.0 if runner_up.score <= 0 else 0.0
    return max(0.0, min(1.0, runner_up.score / top.score))


def _comparison_confidence(items: list[RankedListing]) -> str:
    if not items:
        return "low"
    warning_count = sum(len(item.warnings) for item in items)
    missing_commute_count = sum(1 for item in items if item.listing.commute_minutes is None)
    area_count = sum(1 for item in items if item.listing.area_data and item.listing.area_data.evidence)
    if warning_count == 0 and missing_commute_count == 0 and area_count == len(items):
        return "high"
    if warning_count <= len(items) and missing_commute_count < len(items):
        return "medium"
    return "low"


def _evidence_count(listing: Listing) -> int:
    if listing.area_data is None:
        return 0
    return len(listing.area_data.evidence)
