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

from src.app import build_app
from src.models.schemas import Listing
from src.models.schemas import ExportOptions, ExportPayload, RankedListing
from src.skills.affordability import estimate_monthly_payment
from src.skills.comparison import compare_homes as _compare_homes
from src.skills.export import ExportOrchestrator
from src.skills.intake import parse_buyer_brief
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
    return Listing(
        id=str(d.get("id", "")),
        title=str(d.get("title", "")),
        price=int(d.get("price", 0)),
        bedrooms=int(d.get("bedrooms", 0)),
        bathrooms=int(d.get("bathrooms", 0)),
        location=str(d.get("location", "")),
        commute_minutes=d.get("commute_minutes"),
        features=list(d.get("features") or []),
        description=str(d.get("description", "")),
        source_url=str(d.get("source_url", "")),
    )


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
    ranked = _rank_listings(profile, [_to_listing(l) for l in listings])
    return [
        {
            "listing": asdict(r.listing),
            "score": r.score,
            "matched": r.matched,
            "missed": r.missed,
            "warnings": r.warnings,
        }
        for r in ranked
    ]


@mcp.tool()
def compare_homes(listings: list[dict]) -> str:
    """Generate a side-by-side comparison of up to 5 listings."""
    return _compare_homes([_to_listing(l) for l in listings])


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
def export_csv(ranked_listings: list[dict], output_path: str | None = None) -> dict:
    """Export ranked listings to a CSV file.

    Each ranked listing dict may be either the output from rank_listings or a dict
    containing listing, score, matched, missed, and warnings keys.
    """
    ranked = []
    for item in ranked_listings:
        listing_data = item.get("listing", item)
        ranked.append(
            RankedListing(
                listing=_to_listing(listing_data),
                score=float(item.get("score", 0)),
                matched=list(item.get("matched") or []),
                missed=list(item.get("missed") or []),
                warnings=list(item.get("warnings") or []),
            )
        )
    result = ExportOrchestrator().export(
        ExportPayload(ranked_listings=ranked),
        ExportOptions(format="csv", output_path=output_path),
    )
    return asdict(result)


@mcp.tool()
def export_html(ranked_listings: list[dict], output_path: str | None = None) -> dict:
    """Export ranked listings to a self-contained HTML report."""
    ranked = []
    for item in ranked_listings:
        listing_data = item.get("listing", item)
        ranked.append(
            RankedListing(
                listing=_to_listing(listing_data),
                score=float(item.get("score", 0)),
                matched=list(item.get("matched") or []),
                missed=list(item.get("missed") or []),
                warnings=list(item.get("warnings") or []),
            )
        )
    result = ExportOrchestrator().export(
        ExportPayload(ranked_listings=ranked),
        ExportOptions(format="html", output_path=output_path),
    )
    return asdict(result)


@mcp.tool()
def search_demo_listings(brief: str) -> list[dict]:
    """Search the built-in demo dataset (mock listings across London, Manchester,
    Bristol, Leeds). Useful for testing the harness without a live data source.

    Returns ranked listings matching the brief.
    """
    app = build_app()
    app.intake(brief)
    ranked = app.triage(limit=10)
    return [
        {
            "listing": asdict(r.listing),
            "score": r.score,
            "matched": r.matched,
            "missed": r.missed,
            "warnings": r.warnings,
        }
        for r in ranked
    ]


if __name__ == "__main__":
    mcp.run()
