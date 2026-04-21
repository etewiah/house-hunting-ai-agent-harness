from __future__ import annotations

from src.models.schemas import Listing


def generate_offer_brief(listing: Listing) -> str:
    return "\n".join(
        [
            f"Offer-prep brief for {listing.title}",
            f"Listing price: £{listing.price:,}",
            "Use this to prepare questions for qualified professionals.",
            "Do not treat this as legal, mortgage, survey, inspection, fiduciary, or negotiation advice.",
            "Suggested next step: gather comparables, review disclosures, and speak with appropriate professionals before making an offer.",
        ]
    )
