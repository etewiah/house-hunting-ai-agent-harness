import csv

from src.models.schemas import AreaData, AreaEvidence, BuyerProfile, ExportOptions, ExportPayload, Listing, RankedListing
from src.skills.export.csv_exporter import REQUIRED_COLUMNS
from src.skills.export.export_orchestrator import ExportOrchestrator


def _ranked_listing(commute_minutes: int | None = 30) -> RankedListing:
    listing = Listing(
        id="L1",
        title="Example home",
        price=450000,
        bedrooms=3,
        bathrooms=1,
        location="Example town",
        commute_minutes=commute_minutes,
        features=["garden"],
        description="",
        source_url="https://example.com/listing",
    )
    return RankedListing(
        listing=listing,
        score=87.25,
        matched=["garden", "budget"],
        missed=["parking"],
        warnings=["commute time estimated"],
    )


def test_csv_export_writes_required_columns(tmp_path):
    output_path = tmp_path / "shortlist.csv"
    payload = ExportPayload(ranked_listings=[_ranked_listing()])
    result = ExportOrchestrator().export(
        payload,
        ExportOptions(format="csv", output_path=str(output_path)),
    )

    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert result.format == "csv"
    assert result.listing_count == 1
    assert list(rows[0].keys()) == REQUIRED_COLUMNS
    assert rows[0]["title"] == "Example home"
    assert rows[0]["price"] == "450000"
    assert rows[0]["matched_features"] == "garden;budget"
    assert rows[0]["warnings"] == "commute time estimated"


def test_csv_export_leaves_missing_commute_empty(tmp_path):
    output_path = tmp_path / "shortlist.csv"
    payload = ExportPayload(ranked_listings=[_ranked_listing(commute_minutes=None)])
    ExportOrchestrator().export(payload, ExportOptions(format="csv", output_path=str(output_path)))

    with output_path.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["commute_minutes"] == ""


def test_csv_export_caps_max_listings(tmp_path):
    output_path = tmp_path / "shortlist.csv"
    payload = ExportPayload(ranked_listings=[_ranked_listing(), _ranked_listing()])
    result = ExportOrchestrator().export(
        payload,
        ExportOptions(format="csv", output_path=str(output_path), max_listings=1),
    )

    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert result.listing_count == 1
    assert len(rows) == 1


def test_csv_export_warns_when_profile_context_present(tmp_path):
    output_path = tmp_path / "shortlist.csv"
    payload = ExportPayload(
        buyer_profile=BuyerProfile(location_query="Example", max_budget=500000, min_bedrooms=2),
        ranked_listings=[_ranked_listing()],
    )
    result = ExportOrchestrator().export(
        payload,
        ExportOptions(format="csv", output_path=str(output_path)),
    )

    assert result.warnings


def test_csv_export_includes_extraction_metadata_columns(tmp_path):
    output_path = tmp_path / "shortlist.csv"
    listing = Listing(
        id="L1",
        title="Example home",
        price=450000,
        bedrooms=3,
        bathrooms=1,
        location="Example town",
        commute_minutes=30,
        features=["garden"],
        description="",
        source_url="https://example.com/listing",
        external_refs={"extraction_quality_score": 82, "extraction_parser": "zoopla"},
    )
    payload = ExportPayload(
        ranked_listings=[RankedListing(listing=listing, score=87.25, matched=["garden"], missed=[], warnings=[])],
    )
    ExportOrchestrator().export(payload, ExportOptions(format="csv", output_path=str(output_path)))

    with output_path.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["extraction_quality_score"] == "82"
    assert row["extraction_parser"] == "zoopla"


def test_csv_export_includes_commute_estimation_metadata(tmp_path):
    output_path = tmp_path / "shortlist.csv"
    listing = Listing(
        id="L1",
        title="Example home",
        price=450000,
        bedrooms=3,
        bathrooms=1,
        location="Example town",
        commute_minutes=22,
        features=["garden"],
        description="",
        source_url="https://example.com/listing",
        external_refs={
            "commute_estimation": {
                "destination": "Birmingham New Street",
                "mode": "transit",
            }
        },
    )
    payload = ExportPayload(
        ranked_listings=[RankedListing(listing=listing, score=87.25, matched=["garden"], missed=[], warnings=[])],
    )
    ExportOrchestrator().export(payload, ExportOptions(format="csv", output_path=str(output_path)))

    with output_path.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["commute_estimated"] == "yes"
    assert row["commute_destination"] == "Birmingham New Street"
    assert row["commute_mode"] == "transit"


def test_csv_export_includes_area_metadata_columns(tmp_path):
    output_path = tmp_path / "shortlist.csv"
    listing = Listing(
        id="L1",
        title="Example home",
        price=450000,
        bedrooms=3,
        bathrooms=1,
        location="Example town",
        commute_minutes=22,
        features=["garden"],
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
            warnings=["school distance estimated"],
        ),
    )
    payload = ExportPayload(
        ranked_listings=[RankedListing(listing=listing, score=87.25, matched=["garden"], missed=[], warnings=[])],
    )
    ExportOrchestrator().export(payload, ExportOptions(format="csv", output_path=str(output_path)))

    with output_path.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["area_evidence_count"] == "1"
    assert row["area_top_categories"] == "schools"
    assert row["area_warning_count"] == "1"


def test_csv_export_skips_area_metadata_when_option_disabled(tmp_path):
    output_path = tmp_path / "shortlist.csv"
    listing = Listing(
        id="L1",
        title="Example home",
        price=450000,
        bedrooms=3,
        bathrooms=1,
        location="Example town",
        commute_minutes=22,
        features=["garden"],
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
    payload = ExportPayload(
        ranked_listings=[RankedListing(listing=listing, score=87.25, matched=["garden"], missed=[], warnings=[])],
    )
    ExportOrchestrator().export(
        payload,
        ExportOptions(format="csv", output_path=str(output_path), include_area_data=False),
    )

    with output_path.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["area_evidence_count"] == ""
    assert row["area_top_categories"] == ""
    assert row["area_warning_count"] == ""
