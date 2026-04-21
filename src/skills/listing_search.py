from __future__ import annotations

from src.models.schemas import BuyerProfile, Listing

# Maps commute hub names to the city they belong to, for queries like "King's Cross"
# where the city name itself doesn't appear in the brief.
_HUB_TO_CITY: dict[str, str] = {
    "king's cross": "London",
    "kings cross": "London",
    "london bridge": "London",
    "canary wharf": "London",
    "victoria": "London",
    "waterloo": "London",
    "paddington": "London",
    "euston": "London",
    "temple meads": "Bristol",
}

_KNOWN_CITIES = [
    "London", "Manchester", "Bristol", "Leeds", "Birmingham",
    "Liverpool", "Edinburgh", "Glasgow", "Sheffield", "Newcastle",
]


def _resolve_city(location_query: str) -> str | None:
    lowered = location_query.lower()
    for hub, city in _HUB_TO_CITY.items():
        if hub in lowered:
            return city
    for city in _KNOWN_CITIES:
        if city.lower() in lowered:
            return city
    return None


def filter_listings(profile: BuyerProfile, listings: list[Listing]) -> list[Listing]:
    return [
        listing
        for listing in listings
        if listing.price <= profile.max_budget * 1.1 and listing.bedrooms >= max(1, profile.min_bedrooms - 1)
    ]


def filter_by_location(
    location_query: str, listings: list[Listing]
) -> tuple[list[Listing], list[str]]:
    if location_query == "unknown":
        return listings, []

    city = _resolve_city(location_query)
    if city is None:
        return listings, []

    matched = [listing for listing in listings if city.lower() in listing.location.lower()]
    if matched:
        return matched, []

    return listings, [
        f"No listings found for '{location_query}' in the current dataset "
        f"(looked for '{city}'). Showing all price/bedroom matches instead."
    ]
