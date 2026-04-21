from src.models.schemas import BuyerProfile, Listing
from src.skills.intake import parse_buyer_brief
from src.skills.ranking import rank_listing, rank_listings


def _listing(
    id: str,
    title: str,
    price: int,
    bedrooms: int,
    location: str,
    commute_minutes: int | None,
    features: list[str],
) -> Listing:
    return Listing(
        id=id,
        title=title,
        price=price,
        bedrooms=bedrooms,
        bathrooms=1,
        location=location,
        commute_minutes=commute_minutes,
        features=features,
        description="",
        source_url="https://example.com",
    )


def test_expected_top_listing_for_default_profile():
    profile = parse_buyer_brief(
        "I want a 3-bed within 45 minutes of King's Cross, budget £700k, walkable area, quiet street, decent garden."
    )
    listings = [
        _listing(
            "best",
            "Quiet Garden Terrace",
            675_000,
            3,
            "Walthamstow, London",
            38,
            ["garden", "walkable", "quiet street"],
        ),
        _listing(
            "small",
            "Compact Flat",
            500_000,
            2,
            "Finsbury Park, London",
            25,
            ["walkable"],
        ),
    ]
    ranked = rank_listings(profile, listings)
    assert ranked[0].listing.id == "best"


def test_missing_commute_generates_warning():
    profile = BuyerProfile(
        location_query="test",
        max_budget=700000,
        min_bedrooms=3,
        max_commute_minutes=45,
        must_haves=[],
        nice_to_haves=[],
    )
    listing = Listing(
        id="L999",
        title="Missing commute",
        price=650000,
        bedrooms=3,
        bathrooms=1,
        location="test",
        commute_minutes=None,
        features=[],
        description="",
        source_url="https://example.com",
    )
    result = rank_listing(profile, listing)
    assert "commute time missing" in result.warnings
