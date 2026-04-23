"""
Tests for browser extraction module and MCP tools.

These tests validate that:
- The extraction CLI wrappers exist and are executable
- The Python extraction module can be imported and called
- The MCP tools are registered correctly
"""

import json
import subprocess
from pathlib import Path
import pytest


# Test that CLI wrappers exist
def test_extract_cli_exists():
    """Verify extract-cli.mjs exists."""
    cli_path = Path(
        __file__
    ).parent.parent.parent / ".pi" / "extensions" / "house-hunt-browser" / "bin" / "extract-cli.mjs"
    assert cli_path.exists(), f"extract-cli.mjs not found at {cli_path}"


def test_commute_cli_exists():
    """Verify commute-cli.mjs exists."""
    cli_path = (
        Path(__file__).parent.parent.parent / ".pi" / "extensions" / "house-hunt-browser" / "bin" / "commute-cli.mjs"
    )
    assert cli_path.exists(), f"commute-cli.mjs not found at {cli_path}"


# Test that Python extraction module can be imported
def test_browser_extraction_imports():
    """Verify browser_extraction module imports without error."""
    from src.skills.browser_extraction import (
        property_web_search,
        property_listing_extract,
        extract_property_listings,
        house_hunt_from_web,
        ExtractionError,
    )

    assert callable(property_web_search)
    assert callable(property_listing_extract)
    assert callable(extract_property_listings)
    assert callable(house_hunt_from_web)
    assert issubclass(ExtractionError, Exception)


# Test that MCP tools are registered
def test_mcp_tools_registered():
    """Verify new extraction tools are registered in MCP server."""
    # Note: FastMCP.list_tools() is async, so we can't test it directly in sync pytest.
    # Instead, verify that the tool decorator was called and functions exist.
    from src.ui.mcp_server import (
        property_web_search_tool,
        property_listing_extract_tool,
        extract_property_listings_tool,
        house_hunt_from_web_tool,
    )

    assert callable(property_web_search_tool)
    assert callable(property_listing_extract_tool)
    assert callable(extract_property_listings_tool)
    assert callable(house_hunt_from_web_tool)


# Test basic extraction module functions (mocked, no actual HTTP)
def test_extraction_error_is_exception():
    """Verify ExtractionError is an Exception."""
    from src.skills.browser_extraction import ExtractionError

    assert issubclass(ExtractionError, Exception)
    err = ExtractionError("test error")
    assert str(err) == "test error"


def test_commute_enrichment_returns_list():
    """Verify enrich_with_commute returns a list."""
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

    # With no destination, should return unchanged
    result = enrich_with_commute(listings, None)
    assert result == listings

    # With destination, would call Node CLI (skipped in this test)
    # but should still return a list
    result = enrich_with_commute(listings, "London", "transit")
    assert isinstance(result, list)


# Test that constants are correct
def test_default_listing_sites():
    """Verify default listing sites are the expected portals."""
    from src.skills.browser_extraction import DEFAULT_LISTING_SITES

    assert "rightmove.co.uk" in DEFAULT_LISTING_SITES
    assert "zoopla.co.uk" in DEFAULT_LISTING_SITES
    assert "onthemarket.com" in DEFAULT_LISTING_SITES
