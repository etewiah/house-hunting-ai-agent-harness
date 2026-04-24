from src.models.schemas import AreaData, AreaEvidence, Listing
from src.skills.comparison import build_comparison_result, compare_homes
from src.skills.ranking import rank_listings
from src.models.schemas import BuyerProfile


def test_compare_homes_marks_estimated_commute():
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

    output = compare_homes([listing])

    assert "commute 18 mins (estimated)" in output


def test_compare_homes_includes_area_context_when_available():
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

    output = compare_homes([listing])

    assert "area context:" in output
    assert "schools (estimated): Two schools rated good nearby" in output


def test_structured_comparison_returns_recommendation_and_verification_items():
    profile = BuyerProfile(
        location_query="Birmingham",
        max_budget=300000,
        min_bedrooms=2,
        max_commute_minutes=25,
        must_haves=["parking"],
        nice_to_haves=[],
    )
    listings = [
        Listing(
            id="best",
            title="Best Flat",
            price=250000,
            bedrooms=2,
            bathrooms=1,
            location="Birmingham",
            commute_minutes=18,
            features=["parking"],
            description="",
            source_url="https://example.com/best",
        ),
        Listing(
            id="missing",
            title="Missing Evidence Flat",
            price=245000,
            bedrooms=2,
            bathrooms=1,
            location="Birmingham",
            commute_minutes=None,
            features=["parking"],
            description="",
            source_url="https://example.com/missing",
        ),
    ]
    ranked = rank_listings(profile, listings)

    result = build_comparison_result(ranked, max_listings=2)

    assert result.recommendation_listing_id == "best"
    assert result.trade_offs
    assert any(item.category == "commute" for item in result.verification_items)
    assert any(dimension.name == "price" for dimension in result.dimensions)
