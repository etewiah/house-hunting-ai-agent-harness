from src.models.schemas import AreaData, AreaEvidence, Listing
from src.skills.comparison import compare_homes


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
