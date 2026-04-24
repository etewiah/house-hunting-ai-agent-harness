from src.models.schemas import Listing, PropertyDecisionDetails, SourcedValue
from src.skills.verification import generate_verification_items, verification_summary


def _listing(decision_details=None, commute_minutes=20):
    return Listing(
        id="L1",
        title="Example flat",
        price=300000,
        bedrooms=2,
        bathrooms=1,
        location="Birmingham",
        commute_minutes=commute_minutes,
        features=["parking"],
        description="",
        source_url="https://example.com/listing",
        decision_details=decision_details,
    )


def test_verification_items_call_out_missing_decision_details():
    checks = generate_verification_items(_listing(decision_details=None))

    categories = {item.category for item in checks}
    assert "tenure" in categories
    assert "flood-risk" in categories
    assert any(item.priority == "high" for item in checks)


def test_verification_items_flag_short_lease_and_high_service_charge():
    details = PropertyDecisionDetails(
        tenure=SourcedValue(value="leasehold", source="listing_provided"),
        lease_years_remaining=SourcedValue(value=82, source="listing_provided"),
        service_charge_annual=SourcedValue(value=3600, source="listing_provided"),
        council_tax_band=SourcedValue(value="C", source="listing_provided"),
        epc_rating=SourcedValue(value="C", source="listing_provided"),
        chain_status=SourcedValue(value="no onward chain", source="listing_provided"),
        parking_details=SourcedValue(value="allocated parking", source="listing_provided"),
        flood_risk=SourcedValue(value="not checked", source="estimated"),
    )

    checks = generate_verification_items(_listing(decision_details=details))

    assert any(item.category == "lease" for item in checks)
    assert any(item.category == "running-costs" for item in checks)


def test_verification_summary_counts_high_priority_items():
    summary = verification_summary(_listing(decision_details=None, commute_minutes=None))

    assert summary["listing_id"] == "L1"
    assert summary["verification_count"] >= 1
    assert summary["high_priority_count"] >= 1
    assert summary["items"]
