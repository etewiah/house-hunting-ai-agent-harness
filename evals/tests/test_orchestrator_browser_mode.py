from __future__ import annotations

from src.app import build_app
from src.harness.orchestrator import HouseHuntOrchestrator
from src.models.schemas import AreaData, AreaEvidence, Listing


def _listing(
    id: str,
    title: str,
    price: int,
    bedrooms: int,
    location: str,
    commute_minutes: int | None,
    features: list[str],
) -> Listing:
    return Listing(
        id=id,
        title=title,
        price=price,
        bedrooms=bedrooms,
        bathrooms=1,
        location=location,
        commute_minutes=commute_minutes,
        features=features,
        description="",
        source_url="https://example.com",
    )


def test_build_app_allows_missing_listing_provider(monkeypatch):
    monkeypatch.delenv("H2C_READ_KEY", raising=False)
    monkeypatch.delenv("LISTINGS_CSV_PATH", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    app = build_app()

    assert app.listings is None


def test_orchestrator_can_rank_user_or_browser_supplied_listings_without_provider(tmp_path):
    app = HouseHuntOrchestrator(listings=None, trace_dir=str(tmp_path))
    app.intake("2-bed flat near Birmingham New Street, under £250k, max 25 min commute, parking preferred")

    ranked = app.triage_listings(
        [
            _listing(
                "best",
                "Central Birmingham Apartment",
                240_000,
                2,
                "Birmingham",
                18,
                ["parking"],
            ),
            _listing(
                "overbudget",
                "Luxury Flat",
                290_000,
                2,
                "Birmingham",
                12,
                ["parking"],
            ),
            _listing(
                "wrongcity",
                "Manchester Flat",
                200_000,
                2,
                "Manchester",
                20,
                ["parking"],
            ),
        ]
    )

    assert [item.listing.id for item in ranked] == ["best"]
    assert app.state.triage_warnings == []


def test_triage_without_provider_gives_browser_first_guidance(tmp_path):
    app = HouseHuntOrchestrator(listings=None, trace_dir=str(tmp_path))
    app.intake("2-bed flat near Birmingham New Street, under £250k")

    try:
        app.triage()
    except ValueError as exc:
        assert "triage_listings(candidates)" in str(exc)
    else:
        raise AssertionError("Expected triage() to require a provider or supplied listings")


def test_orchestrator_can_rank_browser_supplied_listing_dicts(tmp_path):
    app = HouseHuntOrchestrator(listings=None, trace_dir=str(tmp_path))
    app.intake("2-bed flat near Birmingham New Street, under £250k, parking preferred")

    ranked = app.triage_listing_dicts(
        [
            {
                "id": "best",
                "title": "Station Quarter Flat",
                "price": 235_000,
                "bedrooms": 2,
                "bathrooms": 1,
                "location": "Birmingham",
                "commute_minutes": 15,
                "features": ["parking"],
                "description": "",
                "source_url": "https://example.com/best",
            },
            {
                "id": "small",
                "title": "Tiny Flat",
                "price": 190_000,
                "bedrooms": 1,
                "bathrooms": 1,
                "location": "Birmingham",
                "commute_minutes": 10,
                "features": ["parking"],
                "description": "",
                "source_url": "https://example.com/small",
            },
        ]
    )

    assert [item.listing.id for item in ranked][0] == "best"
    assert [item.listing.id for item in ranked] == ["best", "small"]


def test_pipeline_status_tracks_stage_history_for_browser_supplied_listings(tmp_path):
    app = HouseHuntOrchestrator(listings=None, trace_dir=str(tmp_path))
    app.intake("2-bed flat near Birmingham New Street, under £250k, parking preferred")

    app.triage_listing_dicts(
        [
            {
                "id": "best",
                "title": "Station Quarter Flat",
                "price": 235_000,
                "bedrooms": 2,
                "bathrooms": 1,
                "location": "Birmingham",
                "commute_minutes": 15,
                "features": ["parking"],
                "description": "",
                "source_url": "https://example.com/best",
            }
        ]
    )

    status = app.get_pipeline_status()

    assert status["current_stage"] == "triage.completed"
    history = status["history"]
    assert isinstance(history, list)
    assert any(item.get("stage") == "intake.completed" for item in history if isinstance(item, dict))
    final_event = history[-1]
    assert final_event["stage"] == "triage.completed"
    assert final_event["metrics"]["ranked_count"] == 1


def test_acquisition_summary_tracks_exclusion_reasons(tmp_path):
    app = HouseHuntOrchestrator(listings=None, trace_dir=str(tmp_path))
    app.intake("2-bed flat near Birmingham New Street, under £250k, parking preferred")

    ranked = app.triage_listing_dicts(
        [
            {
                "id": "best",
                "title": "Station Quarter Flat",
                "price": 235_000,
                "bedrooms": 2,
                "bathrooms": 1,
                "location": "Birmingham",
                "commute_minutes": 15,
                "features": ["parking"],
                "description": "",
                "source_url": "https://example.com/best",
            },
            {
                "id": "out_of_city",
                "title": "Leeds Flat",
                "price": 220_000,
                "bedrooms": 2,
                "bathrooms": 1,
                "location": "Leeds",
                "commute_minutes": 14,
                "features": ["parking"],
                "description": "",
                "source_url": "https://example.com/leeds",
            },
            {
                "id": "over_budget",
                "title": "Birmingham Penthouse",
                "price": 300_000,
                "bedrooms": 2,
                "bathrooms": 1,
                "location": "Birmingham",
                "commute_minutes": 14,
                "features": ["parking"],
                "description": "",
                "source_url": "https://example.com/penthouse",
            },
        ],
        limit=1,
    )

    assert len(ranked) == 1
    summary = app.get_acquisition_summary()
    assert summary["candidate_count"] == 3
    assert summary["located_count"] == 2
    assert summary["filtered_count"] == 1
    assert summary["ranked_count"] == 1
    assert summary["exclusion_reasons"]["location_filter"] == 1
    assert summary["exclusion_reasons"]["requirement_filters"] == 1
    assert summary["exclusion_reasons"]["rank_limit"] == 0


def test_area_context_summary_reports_ranked_listings_with_evidence(tmp_path):
    app = HouseHuntOrchestrator(listings=None, trace_dir=str(tmp_path))
    app.intake("2-bed flat near Birmingham New Street, under £250k")

    with_area = _listing(
        "with_area",
        "Area Context Flat",
        235_000,
        2,
        "Birmingham",
        15,
        ["parking"],
    )
    with_area = Listing(
        id=with_area.id,
        title=with_area.title,
        price=with_area.price,
        bedrooms=with_area.bedrooms,
        bathrooms=with_area.bathrooms,
        location=with_area.location,
        commute_minutes=with_area.commute_minutes,
        features=with_area.features,
        description=with_area.description,
        source_url=with_area.source_url,
        area_data=AreaData(
            listing_id="with_area",
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

    app.triage_listings(
        [
            with_area,
            _listing("no_area", "No Area Flat", 220_000, 2, "Birmingham", 13, ["parking"]),
        ]
    )

    summary = app.get_area_context_summary(max_listings=5)
    assert summary["listing_count_considered"] == 2
    assert summary["listings_with_area_context"] == 1
    assert summary["items"][0]["listing_id"] == "with_area"
    assert "schools" in summary["items"][0]["categories"]


def test_area_evidence_rollup_aggregates_sources_and_totals(tmp_path):
    app = HouseHuntOrchestrator(listings=None, trace_dir=str(tmp_path))
    app.intake("2-bed flat near Birmingham New Street, under £250k")

    first = _listing("first", "First Flat", 235_000, 2, "Birmingham", 15, ["parking"])
    first = Listing(
        id=first.id,
        title=first.title,
        price=first.price,
        bedrooms=first.bedrooms,
        bathrooms=first.bathrooms,
        location=first.location,
        commute_minutes=first.commute_minutes,
        features=first.features,
        description=first.description,
        source_url=first.source_url,
        area_data=AreaData(
            listing_id="first",
            evidence=[
                AreaEvidence(
                    category="schools",
                    summary="Two schools rated good nearby",
                    source_name="Ofsted",
                    source="estimated",
                    retrieved_at="2026-04-23T12:00:00Z",
                ),
                AreaEvidence(
                    category="crime",
                    summary="Crime trend stable",
                    source_name="Police",
                    source="listing_provided",
                    retrieved_at="2026-04-23T12:00:00Z",
                ),
            ],
            warnings=["crime summary inferred"],
        ),
    )

    second = _listing("second", "Second Flat", 220_000, 2, "Birmingham", 13, ["parking"])

    app.triage_listings([first, second])

    rollup = app.get_area_evidence_rollup(max_listings=5)
    assert rollup["listing_count_considered"] == 2
    assert rollup["listings_with_area_context"] == 1
    assert rollup["total_evidence_items"] == 2
    assert rollup["total_area_warnings"] == 1
    assert rollup["evidence_by_source"]["estimated"] == 1
    assert rollup["evidence_by_source"]["listing_provided"] == 1
    assert rollup["confidence_band"] in {"low", "medium", "high"}
    assert rollup["confidence_reason"]
