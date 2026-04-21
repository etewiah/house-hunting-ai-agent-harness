from src.connectors.mock_listing_api import MockListingApi
from src.skills.intake import parse_buyer_brief
from src.skills.ranking import rank_listings


def test_expected_top_listing_for_default_profile():
    profile = parse_buyer_brief(
        "I want a 3-bed within 45 minutes of King's Cross, budget £700k, walkable area, quiet street, decent garden."
    )
    listings = MockListingApi("evals/datasets/listings_small.jsonl").all()
    ranked = rank_listings(profile, listings)
    assert ranked[0].listing.id == "L001"

