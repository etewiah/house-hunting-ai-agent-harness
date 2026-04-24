from __future__ import annotations

from src.models.schemas import Listing, VerificationItem


def generate_verification_items(listing: Listing) -> list[VerificationItem]:
    checks: list[VerificationItem] = []

    if listing.commute_minutes is None:
        checks.append(
            VerificationItem(
                listing_id=listing.id,
                category="commute",
                question="Confirm realistic peak-time commute from the exact address.",
                reason="The listing has no commute time attached.",
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
                reason="The current commute value is estimated.",
                priority="medium",
                source="estimated",
            )
        )

    details = listing.decision_details
    if details is None:
        checks.extend(_missing_detail_checks(listing.id, _core_detail_fields()))
        return checks

    missing_fields = [
        field
        for field in _core_detail_fields()
        if getattr(details, field) is None
    ]
    checks.extend(_missing_detail_checks(listing.id, missing_fields))

    if details.lease_years_remaining is not None:
        try:
            years = int(details.lease_years_remaining.value)
        except (TypeError, ValueError):
            years = None
        if years is not None and years < 85:
            checks.append(
                VerificationItem(
                    listing_id=listing.id,
                    category="lease",
                    question="Ask a conveyancer about lease length implications.",
                    reason=f"Lease years remaining is listed as {years}.",
                    priority="high",
                    source=details.lease_years_remaining.source,
                )
            )

    if details.service_charge_annual is not None:
        try:
            annual_charge = int(details.service_charge_annual.value)
        except (TypeError, ValueError):
            annual_charge = None
        if annual_charge is not None and annual_charge >= 3000:
            checks.append(
                VerificationItem(
                    listing_id=listing.id,
                    category="running-costs",
                    question="Confirm service charge history, planned works, and reserve fund position.",
                    reason=f"Annual service charge is listed as £{annual_charge:,}.",
                    priority="high",
                    source=details.service_charge_annual.source,
                )
            )

    for field_name, sourced in _detail_values(details).items():
        if sourced is None:
            continue
        for warning in sourced.warnings:
            checks.append(
                VerificationItem(
                    listing_id=listing.id,
                    category=field_name.replace("_", "-"),
                    question=f"Verify {field_name.replace('_', ' ')}.",
                    reason=warning,
                    priority="medium",
                    source=sourced.source,
                )
            )

    return checks


def verification_summary(listing: Listing) -> dict[str, object]:
    checks = generate_verification_items(listing)
    priorities = {"high": 0, "medium": 0, "low": 0}
    for check in checks:
        priorities[check.priority] = priorities.get(check.priority, 0) + 1
    return {
        "listing_id": listing.id,
        "verification_count": len(checks),
        "high_priority_count": priorities.get("high", 0),
        "priority_counts": priorities,
        "items": [
            {
                "listing_id": item.listing_id,
                "category": item.category,
                "question": item.question,
                "reason": item.reason,
                "priority": item.priority,
                "source": item.source,
            }
            for item in checks
        ],
    }


def _core_detail_fields() -> list[str]:
    return [
        "tenure",
        "council_tax_band",
        "epc_rating",
        "chain_status",
        "parking_details",
        "flood_risk",
    ]


def _missing_detail_checks(listing_id: str, fields: list[str]) -> list[VerificationItem]:
    labels = {
        "tenure": "Confirm whether the property is freehold, leasehold, or share of freehold.",
        "council_tax_band": "Confirm the council tax band from the local authority.",
        "epc_rating": "Check the EPC rating and expiry date.",
        "chain_status": "Ask the agent about chain status and seller timescales.",
        "parking_details": "Verify exactly what parking is included and whether it is allocated or permitted.",
        "flood_risk": "Check flood-risk sources for the exact address.",
    }
    return [
        VerificationItem(
            listing_id=listing_id,
            category=field.replace("_", "-"),
            question=labels[field],
            reason=f"{field.replace('_', ' ')} is missing from the listing data.",
            priority="medium" if field not in {"tenure", "flood_risk"} else "high",
            source="missing",
        )
        for field in fields
    ]


def _detail_values(details) -> dict[str, object]:
    return {
        "tenure": details.tenure,
        "lease_years_remaining": details.lease_years_remaining,
        "service_charge_annual": details.service_charge_annual,
        "ground_rent_annual": details.ground_rent_annual,
        "council_tax_band": details.council_tax_band,
        "epc_rating": details.epc_rating,
        "chain_status": details.chain_status,
        "parking_details": details.parking_details,
        "outdoor_space": details.outdoor_space,
        "condition_summary": details.condition_summary,
        "floor_area_sqft": details.floor_area_sqft,
        "price_per_sqft": details.price_per_sqft,
        "flood_risk": details.flood_risk,
        "broadband": details.broadband,
    }
