from src.models.schemas import Listing
from src.skills.explanation import explain_ranked_listing
from src.skills.intake import parse_buyer_brief
from src.skills.ranking import rank_listing


def test_explanation_mentions_sources():
    profile = parse_buyer_brief("3-bed under £700k with garden and quiet street")
    listing = Listing(
        id="L001",
        title="Quiet Garden Terrace",
        price=675_000,
        bedrooms=3,
        bathrooms=1,
        location="Walthamstow, London",
        commute_minutes=38,
        features=["garden", "quiet street"],
        description="",
        source_url="https://example.com",
    )
    explanation = explain_ranked_listing(rank_listing(profile, listing))
    assert "Sources:" in explanation
    assert "listing_provided" in explanation
