import csv

from src.ui import mcp_server


def _browser_style_rank_inputs():
    return [
        {
            "id": "best",
            "title": "Station Quarter Flat",
            "price": "£235,000",
            "bedrooms": "2 bedrooms",
            "bathrooms": "1 bathroom",
            "location": "Birmingham",
            "commute_minutes": "15 min",
            "features": "parking",
            "description": "",
            "source_url": "https://example.com/best",
        },
        {
            "id": "small",
            "title": "Tiny Flat",
            "price": "£190,000",
            "bedrooms": "1 bedroom",
            "bathrooms": "1 bathroom",
            "location": "Birmingham",
            "commute_minutes": "10 min",
            "features": ["parking"],
            "description": "",
            "source_url": "https://example.com/small",
        },
    ]


def _browser_style_rank_inputs_with_area_context():
    return [
        {
            "id": "best",
            "title": "Station Quarter Flat",
            "price": "£235,000",
            "bedrooms": "2 bedrooms",
            "bathrooms": "1 bathroom",
            "location": "Birmingham",
            "commute_minutes": "15 min",
            "features": "parking",
            "description": "",
            "source_url": "https://example.com/best",
            "area_data": {
                "evidence": [
                    {
                        "category": "schools",
                        "summary": "Two schools rated good nearby",
                        "source_name": "Ofsted",
                        "source": "estimated",
                        "retrieved_at": "2026-04-23T12:00:00Z",
                    }
                ],
                "warnings": ["school distance estimated"],
            },
        }
    ]


def test_mcp_rank_listings_accepts_browser_style_string_fields():
    ranked = mcp_server.rank_listings(
        "2-bed flat near Birmingham New Street, under £250k, max 25 min commute, parking preferred",
        _browser_style_rank_inputs(),
    )

    assert ranked[0]["listing"]["id"] == "best"
    assert ranked[0]["listing"]["price"] == 235000
    assert ranked[0]["listing"]["commute_minutes"] == 15


def test_mcp_run_house_hunt_returns_structured_browser_first_workflow():
    result = mcp_server.run_house_hunt(
        "2-bed flat near Birmingham New Street, under £250k, max 25 min commute, parking preferred",
        _browser_style_rank_inputs(),
    )

    assert result["buyer_profile"]["max_budget"] == 250000
    assert "acquisition_summary" in result
    assert "area_context_summary" in result
    assert "area_evidence_rollup" in result
    assert result["acquisition_summary"]["candidate_count"] == 2
    assert result["area_context_summary"]["listing_count_considered"] >= 1
    assert result["area_context_summary"]["listings_with_area_context"] == 0
    assert result["area_evidence_rollup"]["total_evidence_items"] == 0
    assert result["ranked_listings"][0]["listing"]["id"] == "best"
    assert result["ranked_listings"][0]["score_breakdown"]["budget"]["status"] == "matched"
    assert result["explanations"]
    assert "Boundary:" in result["comparison"]
    assert result["structured_comparison"]["recommendation_listing_id"] == "best"
    assert result["structured_comparison"]["verification_items"]
    assert result["next_steps"]["affordability"]["listing_id"] == "best"
    assert "negotiation advice" in result["next_steps"]["boundary"]


def test_mcp_run_house_hunt_rolls_up_area_evidence_when_present():
    result = mcp_server.run_house_hunt(
        "2-bed flat near Birmingham New Street, under £250k",
        _browser_style_rank_inputs_with_area_context(),
    )

    assert result["area_context_summary"]["listings_with_area_context"] == 1
    assert result["area_evidence_rollup"]["total_evidence_items"] == 1
    assert result["area_evidence_rollup"]["evidence_by_source"]["estimated"] == 1


def test_mcp_export_csv_respects_max_listings(tmp_path):
    output_path = tmp_path / "shortlist.csv"
    ranked_listings = [
        {
            "listing": {
                "id": "a",
                "title": "First home",
                "price": 200000,
                "bedrooms": 2,
                "bathrooms": 1,
                "location": "Birmingham",
                "commute_minutes": 15,
                "features": ["parking"],
                "description": "",
                "source_url": "https://example.com/a",
            },
            "score": 90,
            "matched": ["parking"],
            "missed": [],
            "warnings": [],
        },
        {
            "listing": {
                "id": "b",
                "title": "Second home",
                "price": 210000,
                "bedrooms": 2,
                "bathrooms": 1,
                "location": "Birmingham",
                "commute_minutes": 20,
                "features": ["garden"],
                "description": "",
                "source_url": "https://example.com/b",
            },
            "score": 80,
            "matched": ["garden"],
            "missed": [],
            "warnings": [],
        },
    ]

    result = mcp_server.export_csv(ranked_listings, output_path=str(output_path), max_listings=1)

    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert result["listing_count"] == 1
    assert len(rows) == 1
    assert rows[0]["title"] == "First home"


def test_mcp_export_html_respects_max_listings_and_boundary_notice(tmp_path):
    output_path = tmp_path / "report.html"
    ranked_listings = [
        {
            "listing": {
                "id": "a",
                "title": "First home",
                "price": 200000,
                "bedrooms": 2,
                "bathrooms": 1,
                "location": "Birmingham",
                "commute_minutes": 15,
                "features": ["parking"],
                "description": "",
                "source_url": "https://example.com/a",
            },
            "score": 90,
            "matched": ["parking"],
            "missed": [],
            "warnings": [],
        },
        {
            "listing": {
                "id": "b",
                "title": "Second home",
                "price": 210000,
                "bedrooms": 2,
                "bathrooms": 1,
                "location": "Birmingham",
                "commute_minutes": 20,
                "features": ["garden"],
                "description": "",
                "source_url": "https://example.com/b",
            },
            "score": 80,
            "matched": ["garden"],
            "missed": [],
            "warnings": [],
        },
    ]

    result = mcp_server.export_html(ranked_listings, output_path=str(output_path), max_listings=1)
    html = output_path.read_text(encoding="utf-8")

    assert result["listing_count"] == 1
    assert "First home" in html
    assert "Second home" not in html
    assert "negotiation advice" in html
    assert "fiduciary" in html


def test_mcp_compare_ranked_homes_returns_structured_decision_payload():
    ranked = mcp_server.rank_listings(
        "2-bed flat near Birmingham New Street, under £250k, max 25 min commute, parking preferred",
        _browser_style_rank_inputs(),
    )

    comparison = mcp_server.compare_ranked_homes(ranked, max_listings=2)

    assert comparison["recommendation_listing_id"] == "best"
    assert comparison["trade_offs"]
    assert comparison["dimensions"]
    assert comparison["verification_items"]
