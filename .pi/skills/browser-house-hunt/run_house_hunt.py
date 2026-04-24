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


def _print_acquisition_summary(summary: dict[str, object]) -> None:
    print("## Acquisition Summary")
    if not summary:
        print("No acquisition summary available.")
        print()
        return
    print(f"- candidates: {summary.get('candidate_count', 0)}")
    print(f"- location matched: {summary.get('located_count', 0)}")
    print(f"- after requirement filters: {summary.get('filtered_count', 0)}")
    print(f"- ranked: {summary.get('ranked_count', 0)}")
    exclusion_reasons = summary.get("exclusion_reasons")
    if isinstance(exclusion_reasons, dict):
        print("- excluded:")
        print(f"  - location_filter: {exclusion_reasons.get('location_filter', 0)}")
        print(f"  - requirement_filters: {exclusion_reasons.get('requirement_filters', 0)}")
        print(f"  - rank_limit: {exclusion_reasons.get('rank_limit', 0)}")
    print()


def _print_area_context_summary(summary: dict[str, object]) -> None:
    print("## Area Context Summary")
    if not summary:
        print("No area context summary available.")
        print()
        return
    print(f"- listings considered: {summary.get('listing_count_considered', 0)}")
    print(f"- listings with area context: {summary.get('listings_with_area_context', 0)}")
    items = summary.get("items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            categories = item.get("categories")
            categories_text = ", ".join(categories) if isinstance(categories, list) else ""
            print(
                f"- {item.get('title', 'unknown')}: evidence={item.get('evidence_count', 0)}, "
                f"categories={categories_text}"
            )
    print()


def _print_area_evidence_rollup(rollup: dict[str, object]) -> None:
    print("## Area Evidence Rollup")
    if not rollup:
        print("No area evidence rollup available.")
        print()
        return
    print(f"- listings considered: {rollup.get('listing_count_considered', 0)}")
    print(f"- listings with area context: {rollup.get('listings_with_area_context', 0)}")
    print(f"- total evidence items: {rollup.get('total_evidence_items', 0)}")
    print(f"- total area warnings: {rollup.get('total_area_warnings', 0)}")
    print(f"- confidence band: {rollup.get('confidence_band', 'unknown')}")
    if rollup.get("confidence_reason"):
        print(f"- confidence note: {rollup.get('confidence_reason')}")
    by_source = rollup.get("evidence_by_source")
    if isinstance(by_source, dict) and by_source:
        rendered = ", ".join([f"{key}={value}" for key, value in sorted(by_source.items())])
        print(f"- by source: {rendered}")
    top_categories = rollup.get("top_categories")
    if isinstance(top_categories, dict) and top_categories:
        rendered = ", ".join([f"{key}={value}" for key, value in top_categories.items()])
        print(f"- top categories: {rendered}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the house-hunt harness on supplied listing JSON.")
    parser.add_argument("--brief", required=True, help="Buyer brief in plain English.")
    parser.add_argument("--listings-file", required=True, help="Path to JSON array of normalized listings.")
    parser.add_argument("--export-html", help="Optional HTML export path.")
    parser.add_argument("--export-csv", help="Optional CSV export path.")
    parser.add_argument(
        "--publish-h2c",
        action="store_true",
        help="Publish the top two verified-photo listings to HomesToCompare.",
    )
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

    _print_acquisition_summary(app.get_acquisition_summary())
    _print_area_context_summary(app.get_area_context_summary())
    _print_area_evidence_rollup(app.get_area_evidence_rollup())
    _print_pipeline_summary(app.get_pipeline_status())

    if args.publish_h2c:
        print("## HomesToCompare")
        h2c_result = app.create_comparison(count=2)
        print(f"- Status: {h2c_result.get('status')}")
        if h2c_result.get("overview_url"):
            print(f"- Overview: {h2c_result.get('overview_url')}")
        if h2c_result.get("photos_url"):
            print(f"- Photos: {h2c_result.get('photos_url')}")
        if h2c_result.get("photos_submitted") is not None:
            print(f"- Photos submitted: {h2c_result.get('photos_submitted')}")
        warnings = h2c_result.get("warnings")
        if isinstance(warnings, list) and warnings:
            print(f"- Warnings: {', '.join(str(item) for item in warnings)}")
        errors = h2c_result.get("errors")
        if isinstance(errors, list) and errors:
            print(f"- Errors: {', '.join(str(item) for item in errors)}")
        print()

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
