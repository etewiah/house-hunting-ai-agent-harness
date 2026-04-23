"""
Tests for browser extraction module and MCP tools.

Covers:
- CLI wrapper existence
- Python module import and callable checks
- MCP tool registration
- Fixture-based parser tests (one per parser: Rightmove, Zoopla, OnTheMarket, generic)
  mirroring the Node extension's test/manifest.mjs
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "datasets" / "extraction_fixtures"
EXTRACT_CLI = (
    Path(__file__).parent.parent.parent
    / ".pi"
    / "extensions"
    / "house-hunt-browser"
    / "bin"
    / "extract-cli.mjs"
)


# ---------------------------------------------------------------------------
# CLI presence
# ---------------------------------------------------------------------------


def test_extract_cli_exists():
    assert EXTRACT_CLI.exists(), f"extract-cli.mjs not found at {EXTRACT_CLI}"


def test_commute_cli_exists():
    cli = EXTRACT_CLI.parent / "commute-cli.mjs"
    assert cli.exists(), f"commute-cli.mjs not found at {cli}"


# ---------------------------------------------------------------------------
# Module-level import and callability
# ---------------------------------------------------------------------------


def test_browser_extraction_imports():
    from src.skills.browser_extraction import (
        ExtractionError,
        extract_property_listings,
        house_hunt_from_web,
        property_listing_extract,
        property_web_search,
    )

    assert callable(property_web_search)
    assert callable(property_listing_extract)
    assert callable(extract_property_listings)
    assert callable(house_hunt_from_web)
    assert issubclass(ExtractionError, Exception)


# ---------------------------------------------------------------------------
# MCP tool callability (sync-safe check against decorated functions)
# ---------------------------------------------------------------------------


def test_mcp_tools_registered():
    from src.ui.mcp_server import (
        extract_property_listings,
        house_hunt_from_web,
        property_listing_extract,
        property_web_search,
    )

    assert callable(property_web_search)
    assert callable(property_listing_extract)
    assert callable(extract_property_listings)
    assert callable(house_hunt_from_web)


# ---------------------------------------------------------------------------
# Unit: error and constant checks (no I/O)
# ---------------------------------------------------------------------------


def test_extraction_error_is_exception():
    from src.skills.browser_extraction import ExtractionError

    assert issubclass(ExtractionError, Exception)
    assert str(ExtractionError("test error")) == "test error"


def test_default_listing_sites():
    from src.skills.browser_extraction import DEFAULT_LISTING_SITES

    assert "rightmove.co.uk" in DEFAULT_LISTING_SITES
    assert "zoopla.co.uk" in DEFAULT_LISTING_SITES
    assert "onthemarket.com" in DEFAULT_LISTING_SITES


def test_commute_enrichment_unchanged_without_destination():
    from src.skills.browser_extraction import enrich_with_commute

    listings = [
        {
            "id": "test-1",
            "title": "Test Property",
            "price": 100000,
            "bedrooms": 2,
            "bathrooms": 1,
            "location": "Birmingham",
            "commute_minutes": None,
            "features": [],
            "description": "Test",
            "source_url": "http://example.com",
        }
    ]
    assert enrich_with_commute(listings, None) == listings


def test_commute_enrichment_returns_list_with_destination():
    from src.skills.browser_extraction import enrich_with_commute

    listings = [
        {
            "id": "test-1",
            "title": "Test Property",
            "price": 100000,
            "bedrooms": 2,
            "bathrooms": 1,
            "location": "Birmingham",
            "commute_minutes": None,
            "features": [],
            "description": "Test",
            "source_url": "http://example.com",
        }
    ]
    result = enrich_with_commute(listings, "London", "transit")
    assert isinstance(result, list)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# Fixture-based parser tests (mirrors Node manifest.mjs)
# ---------------------------------------------------------------------------

# Each entry: (fixture_file, url, expected_dict)
# expected keys: parser, title/title_includes, price/min_price, bedrooms,
#                bathrooms, location/location_includes, features,
#                field_sources, min_quality_score, had_json_ld
FIXTURE_CASES = [
    (
        "rightmove.html",
        "https://www.rightmove.co.uk/properties/123456789",
        {
            "parser": "rightmove",
            "title": "Station Quarter Flat",
            "price": 235000,
            "bedrooms": 2,
            "bathrooms": 1,
            "location": "Birmingham City Centre",
            "features": ["parking", "balcony"],
            "field_sources": {
                "title": "site_specific",
                "price": "site_specific",
                "bedrooms": "site_specific",
                "bathrooms": "site_specific",
                "location": "site_specific",
            },
            "min_quality_score": 85,
        },
    ),
    (
        "zoopla.html",
        "https://www.zoopla.co.uk/for-sale/details/42/",
        {
            "parser": "zoopla",
            "title": "Canal Side Apartment",
            "price": 245000,
            "bedrooms": 2,
            "bathrooms": 2,
            "location": "Birmingham",
            "features": ["garden", "lift"],
            "field_sources": {
                "title": "site_specific",
                "price": "site_specific",
                "bedrooms": "site_specific",
                "bathrooms": "site_specific",
                "location": "site_specific",
            },
            "min_quality_score": 85,
        },
    ),
    (
        "onthemarket.html",
        "https://www.onthemarket.com/details/7/",
        {
            "parser": "onthemarket",
            "title": "Garden View Flat",
            "price": 240000,
            "bedrooms": 2,
            "bathrooms": 1,
            "location": "Edgbaston, Birmingham",
            "features": ["parking", "garden"],
            "had_json_ld": True,
            "field_sources": {
                "title": "site_specific",
                "price": "site_specific",
                "bedrooms": "site_specific",
                "bathrooms": "site_specific",
                "location": "site_specific",
            },
            "min_quality_score": 85,
        },
    ),
    (
        "rightmove_minimal.html",
        "https://www.rightmove.co.uk/properties/555555555",
        {
            "parser": "rightmove",
            "title": "Compact City Flat",
            "price": 199950,
            "bedrooms": 1,
            "bathrooms": 0,
            "location": "Jewellery Quarter, Birmingham",
            "features": [],
            "field_sources": {
                "title": "site_specific",
                "price": "site_specific",
                "bedrooms": "site_specific",
                "location": "site_specific",
            },
            "min_quality_score": 70,
        },
    ),
    (
        "rightmove_duplicate_price.html",
        "https://www.rightmove.co.uk/properties/999999999",
        {
            "parser": "rightmove",
            "title": "Garden Terrace",
            "price": 250000,
            "bedrooms": 3,
            "bathrooms": 2,
            "location": "Kings Heath, Birmingham",
            "features": ["garden", "garage"],
            "field_sources": {
                "title": "site_specific",
                "price": "site_specific",
                "bedrooms": "site_specific",
                "bathrooms": "site_specific",
                "location": "site_specific",
            },
            "min_quality_score": 85,
        },
    ),
    (
        "zoopla_no_baths.html",
        "https://www.zoopla.co.uk/for-sale/details/77/",
        {
            "parser": "zoopla",
            "title": "Warehouse Loft",
            "price": 230000,
            "bedrooms": 2,
            "bathrooms": 0,
            "location": "Digbeth, Birmingham",
            "features": ["walkable"],
            "field_sources": {
                "title": "site_specific",
                "price": "site_specific",
                "bedrooms": "site_specific",
                "location": "site_specific",
            },
            "min_quality_score": 70,
        },
    ),
    (
        "onthemarket_text_fallback.html",
        "https://www.onthemarket.com/details/88/",
        {
            "parser": "onthemarket",
            "title": "Quiet Road Apartment",
            "price": 210000,
            "bedrooms": 2,
            "bathrooms": 1,
            "location_includes": "Harborne",
            "features": ["quiet street", "lift"],
            "field_sources": {
                "title": "site_specific",
                "price": "site_specific",
                "bedrooms": "site_specific",
                "bathrooms": "site_specific",
            },
            "min_quality_score": 70,
        },
    ),
    (
        "generic_jsonld_fallback.html",
        "https://example-homes.test/listings/leafy-court",
        {
            "parser": "generic",
            "title": "Leafy Court Apartment",
            "price": 215000,
            "bedrooms": 2,
            "bathrooms": 1,
            "location": "Moseley, Birmingham",
            "features": ["parking", "balcony", "lift"],
            "had_json_ld": True,
            "field_sources": {
                "title": "json_ld",
                "price": "json_ld",
                "bedrooms": "json_ld",
                "location": "json_ld",
            },
            "min_quality_score": 75,
        },
    ),
    (
        "generic_meta_title_fallback.html",
        "https://example-homes.test/listings/selly-oak-flat",
        {
            "parser": "generic",
            "title": "Selly Oak Balcony Flat",
            "price": 205000,
            "bedrooms": 2,
            "bathrooms": 1,
            "location": "Selly Oak, Birmingham",
            "features": ["parking", "balcony"],
            "field_sources": {
                "title": "meta_og_title",
                "price": "text_regex",
                "bedrooms": "text_regex",
                "bathrooms": "text_regex",
                "location": "text_regex",
                "source_url": "url_input",
            },
            "min_quality_score": 50,
        },
    ),
    (
        "generic_canonical_source_url.html",
        "https://example-homes.test/listings/canon-court?from=search",
        {
            "parser": "generic",
            "title": "Canon Court Flat",
            "price": 212500,
            "bedrooms": 2,
            "bathrooms": 1,
            "location": "Bournville, Birmingham",
            "features": ["balcony"],
            "field_sources": {
                "title": "title_tag",
                "price": "text_regex",
                "bedrooms": "text_regex",
                "bathrooms": "text_regex",
                "location": "text_regex",
                "source_url": "canonical_link",
            },
            "min_quality_score": 55,
        },
    ),
    (
        "generic_jsonld_source_url.html",
        "https://example-homes.test/listings/river-point?raw=1",
        {
            "parser": "generic",
            "title": "River Point Apartment",
            "price": 198000,
            "bedrooms": 1,
            "bathrooms": 1,
            "location": "Digbeth, Birmingham",
            "features": ["lift"],
            "had_json_ld": True,
            "field_sources": {
                "title": "json_ld",
                "price": "json_ld",
                "bedrooms": "json_ld",
                "location": "json_ld",
                "source_url": "json_ld",
            },
            "min_quality_score": 70,
        },
    ),
]


def _run_extract_cli(fixture_file: str, url: str) -> dict:
    """Call extract-cli.mjs on a local fixture file and return parsed JSON."""
    fixture_path = FIXTURES_DIR / fixture_file
    result = subprocess.run(
        ["node", str(EXTRACT_CLI), "--url", url, "--file", str(fixture_path)],
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, (
        f"extract-cli.mjs failed for {fixture_file}:\n"
        f"stdout: {result.stdout.decode()}\n"
        f"stderr: {result.stderr.decode()}"
    )
    return json.loads(result.stdout.decode())


@pytest.mark.parametrize(
    "fixture_file,url,expected",
    [(c[0], c[1], c[2]) for c in FIXTURE_CASES],
    ids=[c[0].replace(".html", "") for c in FIXTURE_CASES],
)
def test_parser_fixture(fixture_file: str, url: str, expected: dict):
    """Run each HTML fixture through extract-cli.mjs and assert expected values."""
    output = _run_extract_cli(fixture_file, url)
    listing = output["listing"]
    diagnostics = output["diagnostics"]

    # Parser
    if allowed := expected.get("allowed_parsers"):
        assert diagnostics["parser"] in allowed
    else:
        assert diagnostics["parser"] == expected["parser"], (
            f"parser: got {diagnostics['parser']!r}, want {expected['parser']!r}"
        )

    # Title
    if title_includes := expected.get("title_includes"):
        assert title_includes in listing["title"]
    else:
        assert listing["title"] == expected["title"]

    # Price
    if min_price := expected.get("min_price"):
        assert listing["price"] >= min_price
    else:
        assert listing["price"] == expected["price"]

    # Bedrooms / bathrooms
    assert listing["bedrooms"] == expected["bedrooms"]
    assert listing["bathrooms"] == expected["bathrooms"]

    # Location
    if location_includes := expected.get("location_includes"):
        assert location_includes in listing["location"]
    else:
        assert listing["location"] == expected["location"]

    # Features
    for feature in expected.get("features", []):
        assert feature in listing["features"], (
            f"feature {feature!r} missing from {listing['features']}"
        )

    # Field sources
    for field, source in expected.get("field_sources", {}).items():
        assert diagnostics["fieldSources"].get(field) == source, (
            f"fieldSources[{field!r}]: got {diagnostics['fieldSources'].get(field)!r}, want {source!r}"
        )

    # JSON-LD presence
    if "had_json_ld" in expected:
        assert diagnostics["hadJsonLd"] == expected["had_json_ld"]

    # Quality floor
    if min_q := expected.get("min_quality_score"):
        assert diagnostics["qualityScore"] >= min_q, (
            f"qualityScore: got {diagnostics['qualityScore']}, want >= {min_q}"
        )
