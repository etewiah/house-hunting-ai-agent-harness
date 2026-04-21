from src.models.schemas import BuyerProfile, ExportOptions, ExportPayload, Listing, RankedListing
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
