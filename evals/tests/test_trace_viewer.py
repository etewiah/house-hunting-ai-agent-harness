"""Tests for the trace viewer."""

from __future__ import annotations

import json

import pytest

from src.ui.trace_viewer import render_trace, render_list, _load


def _make_events(*names: str, base_ts: str = "2026-01-01T10:00:00+00:00") -> list[dict]:
    return [{"at": base_ts, "name": n, "payload": {}} for n in names]


def _intake_event(budget: int = 350000, bedrooms: int = 3) -> dict:
    return {
        "at": "2026-01-01T10:00:00+00:00",
        "name": "intake.profile_created",
        "payload": {
            "location_query": "Manchester",
            "max_budget": budget,
            "min_bedrooms": bedrooms,
            "max_commute_minutes": 30,
            "must_haves": ["garden"],
            "nice_to_haves": [],
            "quiet_street_required": False,
        },
    }


def _ranked_event(count: int = 2) -> dict:
    items = [
        {
            "listing": {
                "id": f"L{i}",
                "title": f"Test Home {i}",
                "price": 300000 + i * 10000,
                "bedrooms": 3,
                "bathrooms": 1,
                "location": "Manchester",
                "commute_minutes": 20 + i,
                "features": ["garden"],
                "description": "",
                "source_url": f"https://example.com/{i}",
                "external_refs": None,
            },
            "score": 80.0 - i * 5,
            "matched": ["garden", "within budget"],
            "missed": [],
            "warnings": [],
        }
        for i in range(1, count + 1)
    ]
    return {
        "at": "2026-01-01T10:00:01+00:00",
        "name": "triage.ranked_listings",
        "payload": items,
    }


# ---------------------------------------------------------------------------
# render_trace
# ---------------------------------------------------------------------------


def test_render_trace_shows_header(tmp_path):
    events = [_intake_event()]
    path = tmp_path / "test.json"
    output = render_trace(events, path)
    assert "Trace:" in output
    assert "Start:" in output
    assert "Duration:" in output
    assert "Events: 1" in output


def test_render_trace_shows_intake_fields(tmp_path):
    events = [_intake_event(budget=450000, bedrooms=4)]
    output = render_trace(events, tmp_path / "t.json")
    assert "Manchester" in output
    assert "£450,000" in output
    assert "4+" in output
    assert "garden" in output


def test_render_trace_shows_ranked_listings(tmp_path):
    events = [_ranked_event(count=3)]
    output = render_trace(events, tmp_path / "t.json")
    assert "3 listing(s) ranked" in output
    assert "Test Home 1" in output
    assert "75/100" in output


def test_render_trace_shows_stages_completed(tmp_path):
    events = [
        _intake_event(),
        _ranked_event(),
        {"at": "2026-01-01T10:00:02+00:00", "name": "triage.explanations", "payload": ["Explanation 1"]},
    ]
    output = render_trace(events, tmp_path / "t.json")
    assert "Stages completed:" in output
    assert "intake" in output
    assert "ranking" in output
    assert "explanations" in output


def test_render_trace_shows_relative_timestamps(tmp_path):
    events = [
        {"at": "2026-01-01T10:00:00+00:00", "name": "intake.profile_created", "payload": {}},
        {"at": "2026-01-01T10:00:02.500000+00:00", "name": "triage.ranked_listings", "payload": []},
    ]
    output = render_trace(events, tmp_path / "t.json")
    assert "+0.000s" in output
    assert "+2.500s" in output


def test_render_trace_empty(tmp_path):
    output = render_trace([], tmp_path / "t.json")
    assert "empty trace" in output


def test_render_trace_guardrails_passed(tmp_path):
    events = [{
        "at": "2026-01-01T10:00:00+00:00",
        "name": "guardrails.checked",
        "payload": {
            "scope": "triage.explanations",
            "results": [{"passed": True, "violations": [], "warnings": []}],
        },
    }]
    output = render_trace(events, tmp_path / "t.json")
    assert "Passed: True" in output
    assert "1 check(s)" in output


def test_render_trace_guardrails_violation_surfaced(tmp_path):
    events = [{
        "at": "2026-01-01T10:00:00+00:00",
        "name": "guardrails.checked",
        "payload": {
            "scope": "next_steps",
            "results": [
                {"passed": False, "violations": ["missing advice boundary notice"], "warnings": []}
            ],
        },
    }]
    output = render_trace(events, tmp_path / "t.json")
    assert "Passed: False" in output
    assert "missing advice boundary notice" in output


def test_render_trace_export_event(tmp_path):
    events = [{
        "at": "2026-01-01T10:00:00+00:00",
        "name": "export.created",
        "payload": {
            "format": "csv",
            "output_path": "/tmp/report.csv",
            "listing_count": 3,
            "file_size_bytes": 1024,
        },
    }]
    output = render_trace(events, tmp_path / "t.json")
    assert "CSV export" in output
    assert "/tmp/report.csv" in output
    assert "3 listings" in output


def test_render_trace_extraction_provenance_in_listings(tmp_path):
    events = [{
        "at": "2026-01-01T10:00:00+00:00",
        "name": "triage.ranked_listings",
        "payload": [{
            "listing": {
                "id": "L1", "title": "Test Home", "price": 250000,
                "bedrooms": 2, "bathrooms": 1, "location": "Birmingham",
                "commute_minutes": 20, "features": [], "description": "",
                "source_url": "https://example.com/1",
                "external_refs": {
                    "extraction_quality_score": 55,
                    "extraction_parser": "generic",
                    "extraction_diagnostics": {"missingFields": ["bathrooms"], "warnings": []},
                },
            },
            "score": 65.0,
            "matched": [],
            "missed": [],
            "warnings": [],
        }],
    }]
    output = render_trace(events, tmp_path / "t.json")
    assert "generic quality 55/100" in output
    assert "unconfirmed: bathrooms" in output


# ---------------------------------------------------------------------------
# render_list
# ---------------------------------------------------------------------------


def test_render_list_empty():
    output = render_list([])
    assert "No trace files found" in output


def test_render_list_shows_filenames(tmp_path):
    f1 = tmp_path / "session.json"
    f2 = tmp_path / "demo.json"
    f1.write_text("[]")
    f2.write_text("[]")
    output = render_list([f1, f2])
    assert "session.json" in output
    assert "demo.json" in output


# ---------------------------------------------------------------------------
# _load
# ---------------------------------------------------------------------------


def test_load_valid_trace(tmp_path):
    path = tmp_path / "trace.json"
    events = [{"at": "2026-01-01T10:00:00+00:00", "name": "intake.profile_created", "payload": {}}]
    path.write_text(json.dumps(events))
    result = _load(path)
    assert result == events


def test_load_invalid_trace_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"not": "an array"}')
    with pytest.raises(ValueError, match="expected a JSON array"):
        _load(path)
