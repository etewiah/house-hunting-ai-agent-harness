from src.models.schemas import AreaData, AreaEvidence, Listing, RankedListing
from src.skills.explanation import explain_ranked_listing


def test_template_explanation_marks_estimated_commute_source():
    listing = Listing(
        id="L1",
        title="Estimated commute home",
        price=300000,
        bedrooms=2,
        bathrooms=1,
        location="Birmingham",
        commute_minutes=18,
        features=["parking"],
        description="",
        source_url="https://example.com/listing",
        external_refs={"commute_estimation": {"destination": "Birmingham New Street", "mode": "transit"}},
    )
    item = RankedListing(listing=listing, score=84.0, matched=["parking"], missed=[], warnings=["commute time estimated"])

    explanation = explain_ranked_listing(item)

    assert "commute is estimated unless marked missing" in explanation
    assert "Warnings: commute time estimated." in explanation


def test_template_explanation_marks_area_context_sources():
    listing = Listing(
        id="L1",
        title="Area context home",
        price=300000,
        bedrooms=2,
        bathrooms=1,
        location="Birmingham",
        commute_minutes=18,
        features=["parking"],
        description="",
        source_url="https://example.com/listing",
        area_data=AreaData(
            listing_id="L1",
            evidence=[
                AreaEvidence(
                    category="schools",
                    summary="Two schools rated good nearby",
                    source_name="Ofsted",
                    source="estimated",
                    retrieved_at="2026-04-23T12:00:00Z",
                )
            ],
        ),
    )
    item = RankedListing(listing=listing, score=84.0, matched=["parking"], missed=[], warnings=[])

    explanation = explain_ranked_listing(item)

    assert "area context is schools:estimated" in explanation
