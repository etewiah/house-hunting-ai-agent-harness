from src.connectors.mock_listing_api import MockListingApi
from src.skills.explanation import explain_ranked_listing
from src.skills.intake import parse_buyer_brief
from src.skills.ranking import rank_listing


def test_explanation_mentions_sources():
    profile = parse_buyer_brief("3-bed under £700k with garden and quiet street")
    listing = MockListingApi("evals/datasets/listings_small.jsonl").get_listing("L001")
    assert listing is not None
    explanation = explain_ranked_listing(rank_listing(profile, listing))
    assert "Sources:" in explanation
    assert "listing_provided" in explanation

