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
from src.skills.comparison import compare_homes as _compare_homes
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
    )


def _serialize_ranked_listing(item: RankedListing) -> dict[str, object]:
    return {
        "listing": asdict(item.listing),
        "score": item.score,
        "matched": item.matched,
        "missed": item.missed,
        "warnings": item.warnings,
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
    next_steps = app.prep_next_steps() if ranked else None
    return {
        "buyer_profile": asdict(profile),
        "triage_warnings": app.state.triage_warnings,
        "ranked_listings": [_serialize_ranked_listing(item) for item in ranked],
        "explanations": explanations,
        "comparison": comparison,
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


if __name__ == "__main__":
    mcp.run()
