from __future__ import annotations

from src.models.schemas import BuyerProfile, Listing


def filter_listings(profile: BuyerProfile, listings: list[Listing]) -> list[Listing]:
    return [
        listing
        for listing in listings
        if listing.price <= profile.max_budget * 1.1 and listing.bedrooms >= max(1, profile.min_bedrooms - 1)
    ]
