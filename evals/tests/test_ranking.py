from src.connectors.mock_listing_api import MockListingApi
from src.models.schemas import BuyerProfile, Listing
from src.skills.intake import parse_buyer_brief
from src.skills.ranking import rank_listing, rank_listings


def test_expected_top_listing_for_default_profile():
    profile = parse_buyer_brief(
        "I want a 3-bed within 45 minutes of King's Cross, budget £700k, walkable area, quiet street, decent garden."
    )
    listings = MockListingApi("evals/datasets/listings_small.jsonl").all()
    ranked = rank_listings(profile, listings)
    assert ranked[0].listing.id == "L001"


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
