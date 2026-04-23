from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.app import build_app
from src.models.schemas import ExportOptions


def _load_candidates(path: str) -> list[dict[str, object]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Listings file must contain a JSON array.")
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Listing at index {index} is not a JSON object.")
    return data


def _print_profile(profile) -> None:
    print("## Buyer Profile")
    print(f"- Location: {profile.location_query}")
    print(f"- Budget: £{profile.max_budget:,}")
    print(f"- Bedrooms: {profile.min_bedrooms}+")
    if profile.max_commute_minutes is not None:
        print(f"- Max commute: {profile.max_commute_minutes} mins")
    print(f"- Must-haves: {', '.join(profile.must_haves) or 'none'}")
    print(f"- Nice-to-haves: {', '.join(profile.nice_to_haves) or 'none'}")
    print()


def _print_ranked(ranked) -> None:
    print("## Ranked Listings")
    if not ranked:
        print("No ranked listings produced.")
        print()
        return
    for i, item in enumerate(ranked, 1):
        listing = item.listing
        commute = "unknown" if listing.commute_minutes is None else f"{listing.commute_minutes} mins"
        commute_estimation = listing.external_refs.get("commute_estimation") if listing.external_refs else None
        if commute_estimation is not None:
            commute = f"{commute} (estimated)"
        print(f"{i}. {listing.title} [{item.score:.0f}/100]")
        print(
            f"   £{listing.price:,} · {listing.bedrooms} bed · {listing.bathrooms} bath · "
            f"{listing.location} · commute {commute}"
        )
        print(f"   URL: {listing.source_url}")
        if item.matched:
            print(f"   + {', '.join(item.matched)}")
        if item.missed:
            print(f"   - Missed: {', '.join(item.missed)}")
        if item.warnings:
            print(f"   ! Warnings: {', '.join(item.warnings)}")
        if commute_estimation and isinstance(commute_estimation, dict):
            print(
                "   ~ Commute estimate: "
                f"to {commute_estimation.get('destination', 'unknown')} via {commute_estimation.get('mode', 'unknown')}"
            )
        extraction_quality = listing.external_refs.get("extraction_quality_score") if listing.external_refs else None
        extraction_parser = listing.external_refs.get("extraction_parser") if listing.external_refs else None
        if extraction_quality is not None or extraction_parser is not None:
            print(
                "   ~ Extraction: "
                f"quality {extraction_quality if extraction_quality is not None else 'unknown'}/100, "
                f"parser {extraction_parser if extraction_parser is not None else 'unknown'}"
            )
        print()


def _print_pipeline_summary(status: dict[str, object]) -> None:
    print("## Pipeline Status")
    history = status.get("history")
    if not isinstance(history, list) or not history:
        print("No stage updates recorded.")
        print()
        return
    for event in history:
        if not isinstance(event, dict):
            continue
        stage = event.get("stage", "unknown")
        message = event.get("message", "")
        print(f"- {stage}: {message}")
        metrics = event.get("metrics")
        if isinstance(metrics, dict) and metrics:
            print(f"  metrics: {json.dumps(metrics, sort_keys=True)}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the house-hunt harness on supplied listing JSON.")
    parser.add_argument("--brief", required=True, help="Buyer brief in plain English.")
    parser.add_argument("--listings-file", required=True, help="Path to JSON array of normalized listings.")
    parser.add_argument("--export-html", help="Optional HTML export path.")
    parser.add_argument("--export-csv", help="Optional CSV export path.")
    args = parser.parse_args()

    candidates = _load_candidates(args.listings_file)

    app = build_app()
    profile = app.intake(args.brief)
    ranked = app.triage_listing_dicts(candidates)
    explanations = app.explain_top_matches()
    comparison = app.compare_top(count=min(3, len(ranked)))

    next_steps = app.prep_next_steps() if ranked else None

    _print_profile(profile)

    if app.state.triage_warnings:
        print("## Search Warnings")
        for warning in app.state.triage_warnings:
            print(f"- {warning}")
        print()

    _print_ranked(ranked)

    print("## Explanations")
    for explanation in explanations:
        print(f"- {explanation}")
    print()

    print("## Comparison")
    print(comparison)
    print()

    _print_pipeline_summary(app.get_pipeline_status())

    if next_steps is not None:
        affordability = next_steps["affordability"]
        print("## Affordability Estimate")
        print(f"- Deposit: £{affordability.deposit:,}")
        print(f"- Loan: £{affordability.loan_amount:,}")
        print(f"- Monthly: ~£{affordability.monthly_payment:,}/month")
        print(f"- Note: {affordability.assumptions[-1]}")
        print()

        print("## Tour Questions")
        for question in next_steps["tour_questions"]:
            print(f"- {question}")
        print()

        print("## Offer Brief")
        print(next_steps["offer_brief"])
        print()

        print("## Boundary")
        print(next_steps["boundary"])
        print()

    if args.export_html:
        result = app.export(ExportOptions(format="html", output_path=args.export_html))
        print(f"HTML export: {result.output_path}")
    if args.export_csv:
        result = app.export(ExportOptions(format="csv", output_path=args.export_csv))
        print(f"CSV export: {result.output_path}")

    trace_path = app.tracer.flush("browser-house-hunt")
    print(f"Trace: {trace_path}")


if __name__ == "__main__":
    main()
