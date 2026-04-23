from src.models.schemas import AreaData, AreaEvidence, BuyerProfile, ExportOptions, ExportPayload, Listing, RankedListing
from src.skills.export.export_orchestrator import ExportOrchestrator


def _ranked_listing(title: str = "Example <home>") -> RankedListing:
    listing = Listing(
        id="L1",
        title=title,
        price=450000,
        bedrooms=3,
        bathrooms=1,
        location="Example town",
        commute_minutes=None,
        features=["garden"],
        description="",
        source_url="https://example.com/listing",
    )
    return RankedListing(listing=listing, score=87.0, matched=["garden"], missed=[], warnings=[])


def test_html_export_writes_self_contained_report(tmp_path):
    output_path = tmp_path / "report.html"
    payload = ExportPayload(
        buyer_profile=BuyerProfile(location_query="Example", max_budget=500000, min_bedrooms=2),
        ranked_listings=[_ranked_listing()],
    )
    result = ExportOrchestrator().export(
        payload,
        ExportOptions(format="html", output_path=str(output_path)),
    )

    html = output_path.read_text(encoding="utf-8")
    assert result.format == "html"
    assert result.listing_count == 1
    assert "<style>" in html
    assert "<script" not in html
    assert "Buyer Profile" in html
    assert "House Hunting Report" in html


def test_html_export_escapes_listing_text(tmp_path):
    output_path = tmp_path / "report.html"
    payload = ExportPayload(ranked_listings=[_ranked_listing()])
    ExportOrchestrator().export(payload, ExportOptions(format="html", output_path=str(output_path)))

    html = output_path.read_text(encoding="utf-8")
    assert "Example &lt;home&gt;" in html
    assert "Example <home>" not in html


def test_html_export_renders_extraction_metadata(tmp_path):
    output_path = tmp_path / "report.html"
    listing = Listing(
        id="L1",
        title="Example home",
        price=450000,
        bedrooms=3,
        bathrooms=1,
        location="Example town",
        commute_minutes=None,
        features=["garden"],
        description="",
        source_url="https://example.com/listing",
        external_refs={"extraction_quality_score": 82, "extraction_parser": "zoopla"},
    )
    payload = ExportPayload(ranked_listings=[RankedListing(listing=listing, score=87.0, matched=["garden"], missed=[], warnings=[])])
    ExportOrchestrator().export(payload, ExportOptions(format="html", output_path=str(output_path)))

    html = output_path.read_text(encoding="utf-8")
    assert "quality 82/100" in html
    assert "parser zoopla" in html


def test_html_export_renders_commute_estimation_metadata(tmp_path):
    output_path = tmp_path / "report.html"
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
        external_refs={"commute_estimation": {"destination": "Birmingham New Street", "mode": "transit"}},
    )
    payload = ExportPayload(ranked_listings=[RankedListing(listing=listing, score=87.0, matched=["garden"], missed=[], warnings=[])])
    ExportOrchestrator().export(payload, ExportOptions(format="html", output_path=str(output_path)))

    html = output_path.read_text(encoding="utf-8")
    assert "estimated toward Birmingham New Street via transit" in html


def test_html_export_renders_extraction_missing_fields(tmp_path):
    output_path = tmp_path / "report.html"
    listing = Listing(
        id="L1",
        title="Example home",
        price=450000,
        bedrooms=3,
        bathrooms=1,
        location="Example town",
        commute_minutes=None,
        features=[],
        description="",
        source_url="https://example.com/listing",
        external_refs={
            "extraction_quality_score": 55,
            "extraction_parser": "generic",
            "extraction_diagnostics": {
                "missingFields": ["bathrooms", "commute_minutes"],
                "warnings": ["price extracted from text only"],
            },
        },
    )
    payload = ExportPayload(ranked_listings=[RankedListing(listing=listing, score=60.0, matched=[], missed=[], warnings=[])])
    ExportOrchestrator().export(payload, ExportOptions(format="html", output_path=str(output_path)))

    html = output_path.read_text(encoding="utf-8")
    assert "unconfirmed: bathrooms, commute_minutes" in html
    assert "price extracted from text only" in html


def test_html_export_renders_commute_inferred_from_brief(tmp_path):
    output_path = tmp_path / "report.html"
    listing = Listing(
        id="L1",
        title="Example home",
        price=450000,
        bedrooms=3,
        bathrooms=1,
        location="Example town",
        commute_minutes=35,
        features=[],
        description="",
        source_url="https://example.com/listing",
        external_refs={
            "commute_estimation": {
                "destination": "London",
                "mode": "transit",
                "source": "estimated",
                "provider": "house-hunt-browser-heuristic",
            }
        },
    )
    payload = ExportPayload(ranked_listings=[RankedListing(listing=listing, score=75.0, matched=[], missed=[], warnings=[])])
    ExportOrchestrator().export(payload, ExportOptions(format="html", output_path=str(output_path)))

    html = output_path.read_text(encoding="utf-8")
    assert "estimated toward London via transit" in html
    assert "inferred from brief" in html


def test_html_export_caps_max_listings_in_rendered_output(tmp_path):
    output_path = tmp_path / "report.html"
    payload = ExportPayload(ranked_listings=[_ranked_listing("First home"), _ranked_listing("Second home")])

    result = ExportOrchestrator().export(
        payload,
        ExportOptions(format="html", output_path=str(output_path), max_listings=1),
    )

    html = output_path.read_text(encoding="utf-8")
    assert result.listing_count == 1
    assert "First home" in html
    assert "Second home" not in html


def test_html_export_renders_acquisition_summary_when_present(tmp_path):
    output_path = tmp_path / "report.html"
    payload = ExportPayload(
        ranked_listings=[_ranked_listing("First home")],
        generated_outputs={
            "acquisition_summary": {
                "candidate_count": 6,
                "located_count": 4,
                "filtered_count": 3,
                "ranked_count": 2,
                "exclusion_reasons": {
                    "location_filter": 2,
                    "requirement_filters": 1,
                    "rank_limit": 1,
                },
            }
        },
    )

    ExportOrchestrator().export(payload, ExportOptions(format="html", output_path=str(output_path)))

    html = output_path.read_text(encoding="utf-8")
    assert "Acquisition Summary" in html
    assert "Candidates:" in html
    assert "location filter 2" in html


def test_html_export_renders_area_context_when_enabled(tmp_path):
    output_path = tmp_path / "report.html"
    listing = Listing(
        id="L1",
        title="Area context home",
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
        ranked_listings=[RankedListing(listing=listing, score=87.0, matched=["garden"], missed=[], warnings=[])],
    )

    ExportOrchestrator().export(payload, ExportOptions(format="html", output_path=str(output_path)))

    html = output_path.read_text(encoding="utf-8")
    assert "Area context:" in html
    assert "schools (estimated): Two schools rated good nearby" in html


def test_html_export_renders_area_rollup_when_present(tmp_path):
    output_path = tmp_path / "report.html"
    payload = ExportPayload(
        ranked_listings=[_ranked_listing("First home")],
        generated_outputs={
            "area_evidence_rollup": {
                "listings_with_area_context": 2,
                "total_evidence_items": 3,
                "total_area_warnings": 1,
                "confidence_band": "medium",
                "confidence_reason": "Some ranked listings include area evidence, but coverage is partial.",
                "evidence_by_source": {"estimated": 2, "listing_provided": 1},
            }
        },
    )

    result = ExportOrchestrator().export(payload, ExportOptions(format="html", output_path=str(output_path)))

    html = output_path.read_text(encoding="utf-8")
    assert "Area Evidence Rollup" in html
    assert "Total evidence items:" in html
    assert "Confidence band:" in html
    assert "medium" in html
    assert "estimated=2" in html
    assert any("Area evidence rollup: 3 evidence items across 2 listings" in w for w in result.warnings)
    assert any("confidence=medium" in w for w in result.warnings)
