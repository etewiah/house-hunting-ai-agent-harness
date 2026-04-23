from __future__ import annotations

from src.app import build_app
from src.harness.orchestrator import HouseHuntOrchestrator
from src.models.schemas import Listing


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
