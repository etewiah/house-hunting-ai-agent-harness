from src.models.schemas import Listing
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
