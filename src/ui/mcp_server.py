"""
Optional MCP server exposing house-hunting harness tools to compatible clients.

The client provides listing data from browsing, platform APIs, or any source. The harness
provides structure: scoring, comparison, affordability, guardrails, tracing.

Start with:
  uv run house-hunt serve
"""
from __future__ import annotations

from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from src.harness.orchestrator import HouseHuntOrchestrator
from src.models.schemas import Listing
from src.models.schemas import ExportOptions, ExportPayload, RankedListing
from src.skills.affordability import estimate_monthly_payment
from src.skills.browser_extraction import (
    property_web_search as _property_web_search,
    property_listing_extract as _property_listing_extract,
    extract_property_listings as _extract_property_listings,
    house_hunt_from_web as _house_hunt_from_web,
    ExtractionError,
)
from src.skills.comparison import compare_homes as _compare_homes
from src.skills.comparison import build_comparison_result as _build_comparison_result
from src.skills.export import ExportOrchestrator
from src.skills.intake import parse_buyer_brief
from src.skills.listing_input import listing_from_dict
from src.skills.offer_brief import generate_offer_brief
from src.skills.ranking import rank_listings as _rank_listings
from src.skills.tour_prep import generate_tour_questions

mcp = FastMCP(
    "house-hunt",
    instructions=(
        "House-hunting assistant harness. You supply the listings (from web search, "
        "H2C API, or any source). Call parse_brief first, then rank_listings, then "
        "use the other tools to prepare the buyer's next steps."
    ),
)


def _to_listing(d: dict) -> Listing:
    return listing_from_dict(d)


def _to_ranked_listing(item: dict) -> RankedListing:
    listing_data = item.get("listing", item)
    return RankedListing(
        listing=_to_listing(listing_data),
        score=float(item.get("score", 0)),
        matched=[str(value) for value in list(item.get("matched") or [])],
        missed=[str(value) for value in list(item.get("missed") or [])],
        warnings=[str(value) for value in list(item.get("warnings") or [])],
        score_breakdown=dict(item.get("score_breakdown") or {}),
    )


def _serialize_ranked_listing(item: RankedListing) -> dict[str, object]:
    return {
        "listing": asdict(item.listing),
        "score": item.score,
        "matched": item.matched,
        "missed": item.missed,
        "warnings": item.warnings,
        "score_breakdown": item.score_breakdown,
    }


@mcp.tool()
def parse_brief(brief: str) -> dict:
    """Parse a buyer's natural language brief into a structured profile.

    Returns: location_query, max_budget, min_bedrooms, max_commute_minutes,
    must_haves, nice_to_haves, quiet_street_required.
    """
    profile = parse_buyer_brief(brief)
    return asdict(profile)


@mcp.tool()
def rank_listings(brief: str, listings: list[dict]) -> list[dict]:
    """Score and rank listings against a buyer brief.

    Each listing dict must have: id (str), title (str), price (int),
    bedrooms (int), bathrooms (int), location (str),
    commute_minutes (int or null), features (list[str]),
    description (str), source_url (str).

    Returns listings sorted by score descending, each with matched/missed/warnings.
    """
    profile = parse_buyer_brief(brief)
    ranked = _rank_listings(profile, [_to_listing(listing) for listing in listings])
    return [_serialize_ranked_listing(r) for r in ranked]


@mcp.tool()
def run_house_hunt(brief: str, listings: list[dict], limit: int = 5) -> dict:
    """Run the browser-first house-hunt workflow on supplied listings.

    This parses the brief, filters and ranks the supplied listings, generates
    explanations, creates a comparison summary, and prepares next steps for the
    top match when available.
    """
    app = HouseHuntOrchestrator(listings=None)
    profile = app.intake(brief)
    ranked = app.triage_listing_dicts(listings, limit=limit)
    explanations = app.explain_top_matches()
    comparison = app.compare_top(count=min(3, len(ranked)))
    structured_comparison = app.compare_top_structured(count=min(3, len(ranked)))
    next_steps = app.prep_next_steps() if ranked else None
    return {
        "buyer_profile": asdict(profile),
        "acquisition_summary": app.get_acquisition_summary(),
        "area_context_summary": app.get_area_context_summary(max_listings=limit),
        "area_evidence_rollup": app.get_area_evidence_rollup(max_listings=limit),
        "triage_warnings": app.state.triage_warnings,
        "ranked_listings": [_serialize_ranked_listing(item) for item in ranked],
        "explanations": explanations,
        "comparison": comparison,
        "structured_comparison": structured_comparison,
        "next_steps": None if next_steps is None else {
            "boundary": next_steps["boundary"],
            "affordability": asdict(next_steps["affordability"]),
            "tour_questions": next_steps["tour_questions"],
            "offer_brief": next_steps["offer_brief"],
        },
    }


@mcp.tool()
def compare_homes(listings: list[dict]) -> str:
    """Generate a side-by-side comparison of up to 5 listings."""
    return _compare_homes([_to_listing(listing) for listing in listings])


@mcp.tool()
def compare_ranked_homes(ranked_listings: list[dict], max_listings: int = 3) -> dict:
    """Generate a structured comparison for ranked homes.

    Returns a recommendation, visible trade-offs, possible deal-breakers, source-aware
    comparison dimensions, and verification questions.
    """
    result = _build_comparison_result(
        [_to_ranked_listing(item) for item in ranked_listings],
        max_listings=max_listings,
    )
    return {
        "recommendation_listing_id": result.recommendation_listing_id,
        "recommendation_summary": result.recommendation_summary,
        "close_call_score": result.close_call_score,
        "confidence": result.confidence,
        "warnings": result.warnings,
        "trade_offs": result.trade_offs,
        "deal_breakers": result.deal_breakers,
        "dimensions": [
            {
                "name": item.name,
                "winner_listing_id": item.winner_listing_id,
                "summaries": item.summaries,
                "source": item.source,
                "confidence": item.confidence,
                "warnings": item.warnings,
            }
            for item in result.dimensions
        ],
        "verification_items": [
            {
                "listing_id": item.listing_id,
                "category": item.category,
                "question": item.question,
                "reason": item.reason,
                "priority": item.priority,
                "source": item.source,
            }
            for item in result.verification_items
        ],
    }


@mcp.tool()
def estimate_affordability(price: int, deposit_percent: float = 0.15) -> dict:
    """Estimate monthly mortgage payment.

    Returns deposit, loan_amount, monthly_payment, and assumptions.
    Assumptions: 5.25% annual rate, 25-year term. Not financial advice.
    """
    dummy = Listing(
        id="", title="", price=price, bedrooms=0, bathrooms=0,
        location="", commute_minutes=None, features=[], description="", source_url="",
    )
    return asdict(estimate_monthly_payment(dummy, deposit_percent=deposit_percent))


@mcp.tool()
def tour_questions(listing: dict) -> list[str]:
    """Generate property-specific questions to ask on a viewing."""
    return generate_tour_questions(_to_listing(listing))


@mcp.tool()
def offer_brief(listing: dict) -> str:
    """Generate an offer preparation brief for a listing.

    Not legal, mortgage, or negotiation advice.
    """
    return generate_offer_brief(_to_listing(listing))


@mcp.tool()
def export_csv(
    ranked_listings: list[dict],
    output_path: str | None = None,
    max_listings: int = 5,
) -> dict:
    """Export ranked listings to a CSV file.

    Each ranked listing dict may be either the output from rank_listings or a dict
    containing listing, score, matched, missed, and warnings keys.
    """
    ranked = [_to_ranked_listing(item) for item in ranked_listings]
    result = ExportOrchestrator().export(
        ExportPayload(ranked_listings=ranked),
        ExportOptions(format="csv", output_path=output_path, max_listings=max_listings),
    )
    return asdict(result)


@mcp.tool()
def export_html(
    ranked_listings: list[dict],
    output_path: str | None = None,
    max_listings: int = 5,
) -> dict:
    """Export ranked listings to a self-contained HTML report."""
    ranked = [_to_ranked_listing(item) for item in ranked_listings]
    result = ExportOrchestrator().export(
        ExportPayload(ranked_listings=ranked),
        ExportOptions(format="html", output_path=output_path, max_listings=max_listings),
    )
    return asdict(result)


# Tier 2: Browser-assisted extraction tools

@mcp.tool()
def property_web_search(
    query: str,
    max_results: int = 8,
    sites: list[str] | None = None,
) -> dict:
    """Search the web for property listing URLs on Rightmove, Zoopla, OnTheMarket, etc.

    Args:
        query: Search query or buyer brief for finding listings
        max_results: Max results to return (1-20, default 8)
        sites: Optional domain list (defaults to major UK portals)

    Returns:
        Dict with 'results' list containing {title, url} objects and 'count'.
    """
    try:
        results = _property_web_search(query, max_results, sites)
        return {"results": results, "count": len(results)}
    except ExtractionError as e:
        return {"error": str(e), "results": [], "count": 0}


@mcp.tool()
def property_listing_extract(
    url: str,
    commute_minutes: int | None = None,
) -> dict:
    """Fetch a property listing page and extract normalized listing fields.

    Calls the Pi extension's site-specific parsers (Rightmove, Zoopla, OnTheMarket)
    with JSON-LD fallback. Returns normalized listing and extraction diagnostics.

    Args:
        url: Property listing URL
        commute_minutes: Optional known commute time (overrides estimation)

    Returns:
        Dict with 'listing', 'diagnostics', 'quality', 'missing_fields', 'warnings'.
    """
    try:
        result = _property_listing_extract(url, commute_minutes)
        diagnostics = result.diagnostics
        return {
            "listing": result.listing,
            "diagnostics": diagnostics,
            "quality": diagnostics.get("qualityScore", 0),
            "missing_fields": diagnostics.get("missingFields", []),
            "warnings": diagnostics.get("warnings", []),
            "parser": diagnostics.get("parser", "unknown"),
        }
    except ExtractionError as e:
        return {"error": str(e), "listing": None, "quality": 0}


@mcp.tool()
def extract_property_listings(
    urls: list[str],
    commute_minutes_by_url: dict[str, int] | None = None,
) -> dict:
    """Batch extraction of property listings from multiple URLs.

    Args:
        urls: List of property listing URLs (max 20)
        commute_minutes_by_url: Optional mapping of URL to known commute time

    Returns:
        Dict with 'extracted' (list of results), 'failed' (list of errors), 'count'.
    """
    result = _extract_property_listings(urls, commute_minutes_by_url)
    return {
        "extracted": result["extracted"],
        "failed": result["failed"],
        "extracted_count": len(result["extracted"]),
        "failed_count": len(result["failed"]),
    }


@mcp.tool()
def house_hunt_from_web(
    brief: str,
    max_results: int = 6,
    sites: list[str] | None = None,
    min_quality_score: int = 45,
    commute_destination: str | None = None,
    commute_mode: str = "transit",
) -> dict:
    """End-to-end house hunt: search, extract, enrich commute, filter by quality, rank.

    This tool runs the full browser-assisted flow: discovers candidate listings on the
    web, extracts and normalizes them with quality scoring, enriches with heuristic
    commute times, and filters by minimum quality before returning accepted listings.

    Args:
        brief: Buyer brief in plain English
        max_results: Max search results to extract (1-12, default 6)
        sites: Optional domain whitelist (defaults to Rightmove, Zoopla, OnTheMarket)
        min_quality_score: Minimum extraction quality to accept (0-100, default 45)
        commute_destination: Optional commute destination for enrichment (e.g. London)
        commute_mode: Commute mode for heuristic enrichment (transit/driving/walking)

    Returns:
        Dict with 'search_results', 'extracted', 'accepted_listings', 'failed',
        'average_quality', 'filtered_out_low_quality', and commute metadata.
    """
    result = _house_hunt_from_web(
        brief,
        max_results,
        sites,
        min_quality_score,
        commute_destination,
        commute_mode,
    )
    return {
        "search_results": result.get("search_results", []),
        "search_count": len(result.get("search_results", [])),
        "extracted": result.get("extracted", []),
        "extracted_count": len(result.get("extracted", [])),
        "accepted_listings": result.get("accepted_listings", []),
        "accepted_count": len(result.get("accepted_listings", [])),
        "failed": result.get("failed", []),
        "failed_count": len(result.get("failed", [])),
        "average_quality": result.get("average_quality", 0),
        "filtered_out_low_quality": result.get("filtered_out_low_quality", []),
        "commute_destination": result.get("commute_destination"),
        "commute_destination_inferred": result.get("commute_destination_inferred", False),
        "commute_mode": result.get("commute_mode"),
        "min_quality_score": result.get("min_quality_score"),
    }


if __name__ == "__main__":
    mcp.run()
