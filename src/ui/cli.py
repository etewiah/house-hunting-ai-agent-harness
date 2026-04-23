import argparse

from src.app import build_app
from src.models.schemas import AffordabilityEstimate, BuyerProfile, RankedListing

_WELCOME = """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  House Hunting Agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Describe what you're looking for in plain English.
Include budget, bedrooms, location or commute, and must-haves.

Example:
  3-bed house near Manchester Piccadilly, budget £350k, need a garden, max 30 min commute

"""


def _fmt_profile(profile: BuyerProfile) -> str:
    lines = [f"  Location:      {profile.location_query}"]
    lines.append(f"  Budget:        £{profile.max_budget:,}")
    lines.append(f"  Bedrooms:      {profile.min_bedrooms}+")
    if profile.max_commute_minutes:
        lines.append(f"  Commute:       {profile.max_commute_minutes} mins max")
    if profile.must_haves:
        lines.append(f"  Must-haves:    {', '.join(profile.must_haves)}")
    if profile.nice_to_haves:
        lines.append(f"  Nice-to-haves: {', '.join(profile.nice_to_haves)}")
    return "\n".join(lines)


def _fmt_ranked(items: list[RankedListing]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        listing = item.listing
        commute = (
            "?" if listing.commute_minutes is None else f"{listing.commute_minutes} min"
        )
        lines.append(f"{i}. {listing.title}  [{item.score:.0f}/100]")
        lines.append(
            f"   {listing.location} · £{listing.price:,} · {listing.bedrooms} bed · "
            f"{listing.bathrooms} bath · {commute} commute"
        )
        if item.matched:
            lines.append(f"   + {', '.join(item.matched)}")
        if item.missed:
            lines.append(f"   - Missed: {', '.join(item.missed)}")
        if item.warnings:
            lines.append(f"   ! {', '.join(item.warnings)}")
        lines.append("")
    return "\n".join(lines)


def _fmt_affordability(est: AffordabilityEstimate) -> str:
    return "\n".join([
        f"  Deposit:  £{est.deposit:,}",
        f"  Loan:     £{est.loan_amount:,}",
        f"  Monthly:  ~£{est.monthly_payment:,}/month",
        f"  ({est.assumptions[0]}, {est.assumptions[1]}, {est.assumptions[2]})",
        f"  Note: {est.assumptions[3]}",
    ])


def _print_pipeline_summary(status: dict[str, object]) -> None:
    print("Pipeline status summary:\n")
    history = status.get("history")
    if not isinstance(history, list) or not history:
        print("  (no stage updates recorded)\n")
        return
    for event in history:
        if not isinstance(event, dict):
            continue
        stage = event.get("stage", "unknown")
        message = event.get("message", "")
        print(f"  - {stage}: {message}")
        metrics = event.get("metrics")
        if isinstance(metrics, dict) and metrics:
            rendered_metrics = ", ".join([f"{k}={v}" for k, v in metrics.items()])
            print(f"    ({rendered_metrics})")
    print()


def _print_acquisition_summary(summary: dict[str, object]) -> None:
    print("Acquisition summary:\n")
    if not summary:
        print("  (no acquisition summary available)\n")
        return
    print(f"  - candidates: {summary.get('candidate_count', 0)}")
    print(f"  - location matched: {summary.get('located_count', 0)}")
    print(f"  - after requirement filters: {summary.get('filtered_count', 0)}")
    print(f"  - ranked: {summary.get('ranked_count', 0)}")

    exclusion_reasons = summary.get("exclusion_reasons")
    if isinstance(exclusion_reasons, dict):
        print("  - excluded:")
        print(f"    location_filter={exclusion_reasons.get('location_filter', 0)}")
        print(f"    requirement_filters={exclusion_reasons.get('requirement_filters', 0)}")
        print(f"    rank_limit={exclusion_reasons.get('rank_limit', 0)}")
    print()


def _print_area_context_summary(summary: dict[str, object]) -> None:
    print("Area context summary:\n")
    if not summary:
        print("  (no area context summary available)\n")
        return
    print(f"  - listings considered: {summary.get('listing_count_considered', 0)}")
    print(f"  - listings with area context: {summary.get('listings_with_area_context', 0)}")
    items = summary.get("items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "unknown")
            evidence_count = item.get("evidence_count", 0)
            categories = item.get("categories")
            categories_text = ", ".join(categories) if isinstance(categories, list) else ""
            print(f"  - {title}: evidence={evidence_count}, categories={categories_text}")
    print()


def _print_area_evidence_rollup(rollup: dict[str, object]) -> None:
    print("Area evidence rollup:\n")
    if not rollup:
        print("  (no area evidence rollup available)\n")
        return
    print(f"  - listings considered: {rollup.get('listing_count_considered', 0)}")
    print(f"  - listings with area context: {rollup.get('listings_with_area_context', 0)}")
    print(f"  - total evidence items: {rollup.get('total_evidence_items', 0)}")
    print(f"  - total area warnings: {rollup.get('total_area_warnings', 0)}")
    print(f"  - confidence band: {rollup.get('confidence_band', 'unknown')}")
    if rollup.get("confidence_reason"):
        print(f"  - confidence note: {rollup.get('confidence_reason')}")
    by_source = rollup.get("evidence_by_source")
    if isinstance(by_source, dict) and by_source:
        rendered = ", ".join([f"{key}={value}" for key, value in sorted(by_source.items())])
        print(f"  - by source: {rendered}")
    top_categories = rollup.get("top_categories")
    if isinstance(top_categories, dict) and top_categories:
        rendered = ", ".join([f"{key}={value}" for key, value in top_categories.items()])
        print(f"  - top categories: {rendered}")
    print()


def run_interactive() -> None:
    print(_WELCOME)

    app = build_app()

    if app.llm is not None:
        print("AI intake enabled. Type your search below.\n")
    else:
        print("Regex intake enabled. Set ANTHROPIC_API_KEY for AI-powered intake.\n")

    if app.listings is None:
        print(
            "No listing provider configured for the standalone CLI. "
            "This harness can still be used by a coding agent that finds listings with browser tools "
            "and passes them into app.triage_listings(...).\n"
        )

    while True:
        try:
            brief = input("Your brief: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

        if not brief:
            print("Please enter a description of what you're looking for.\n")
            continue

        profile = app.intake(brief)

        print("\nHere's what I understood:\n")
        print(_fmt_profile(profile))
        print()

        try:
            confirm = input("Does that look right? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

        if confirm in ("", "y", "yes"):
            break
        print("\nLet's try again — be as specific as you like.\n")

    print("\nSearching listings...\n")
    try:
        ranked = app.triage(limit=5)
    except ValueError as exc:
        print(str(exc))
        return

    for warning in app.state.triage_warnings:
        print(f"Note: {warning}\n")

    if not ranked:
        print("No listings matched your brief from the configured listing provider.")
        print("Try relaxing your budget or commute requirements.")
        return

    print(f"Found {len(ranked)} match{'es' if len(ranked) != 1 else ''}:\n")
    print(_fmt_ranked(ranked))

    print("─" * 50)
    print("\nWhy they matched:\n")
    for explanation in app.explain_top_matches():
        print(f"  {explanation}\n")

    print("─" * 50)
    print("\nSide-by-side comparison:\n")
    print(app.compare_top(count=min(3, len(ranked))))

    print("─" * 50)
    next_steps = app.prep_next_steps()

    print("\nAffordability estimate (top match):\n")
    print(_fmt_affordability(next_steps["affordability"]))

    print("\nQuestions to ask on the tour:\n")
    for q in next_steps["tour_questions"]:
        print(f"  • {q}")

    print(f"\n{next_steps['boundary']}\n")

    _print_acquisition_summary(app.get_acquisition_summary())
    _print_area_context_summary(app.get_area_context_summary())
    _print_area_evidence_rollup(app.get_area_evidence_rollup())
    _print_pipeline_summary(app.get_pipeline_status())

    trace_path = app.tracer.flush("session")
    print(f"Session trace saved to {trace_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="house-hunt",
        description="House hunting assistant — describe what you want, get ranked matches.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="search",
        choices=["search", "serve", "trace"],
        help=(
            "'search' (default) starts an interactive session; "
            "'serve' starts the optional MCP server; "
            "'trace' inspects a saved session trace"
        ),
    )
    parser.add_argument(
        "--export-path",
        help="Reserved for future non-interactive export commands.",
    )
    parser.add_argument(
        "--trace-path",
        help="Path to a trace file (used with 'trace' command; defaults to most recent).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available trace files (used with 'trace' command).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Dump raw trace JSON (used with 'trace' command).",
    )
    args = parser.parse_args()
    if args.command == "serve":
        from src.ui.mcp_server import mcp
        mcp.run()
    elif args.command == "trace":
        from src.ui.trace_viewer import main as trace_main
        trace_main(path_arg=args.trace_path, list_only=args.list, raw_json=args.json)
    else:
        run_interactive()


if __name__ == "__main__":
    main()
