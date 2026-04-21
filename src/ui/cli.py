import argparse
from src.app import build_app
from src.models.schemas import AffordabilityEstimate, BuyerProfile, ExportOptions, RankedListing

DEFAULT_BRIEF = (
    "I want a 3-bed within 45 minutes of King's Cross, budget £700k, "
    "walkable area, quiet street, decent garden."
)

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


def run_interactive() -> None:
    print(_WELCOME)

    app = build_app()
    if app.llm is not None:
        print("Powered by Claude. Type your search below.\n")
    else:
        print("Demo mode (mock data, regex parsing).")
        print("Set ANTHROPIC_API_KEY for AI-powered search.\n")

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
    ranked = app.triage(limit=5)

    for warning in app.state.triage_warnings:
        print(f"Note: {warning}\n")

    if not ranked:
        print("No listings matched your brief in the current dataset.")
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

    trace_path = app.tracer.flush("session")
    print(f"Session trace saved to {trace_path}")


def run_demo(export_path: str | None = None) -> None:
    print(f"Demo brief: {DEFAULT_BRIEF!r}\n")
    app = build_app()
    profile = app.intake(DEFAULT_BRIEF)
    ranked = app.triage(limit=3)
    explanations = app.explain_top_matches()
    comparison = app.compare_top(count=3)
    next_steps = app.prep_next_steps()
    export_result = None
    if export_path is not None:
        export_format = "html" if export_path.endswith(".html") else "csv"
        export_result = app.export(ExportOptions(format=export_format, output_path=export_path))
    trace_path = app.tracer.flush("demo")

    print("## Buyer Profile\n")
    print(_fmt_profile(profile))
    print("\n## Ranked Listings\n")
    print(_fmt_ranked(ranked))
    print("## Explanations\n")
    for explanation in explanations:
        print(f"  {explanation}\n")
    print("## Comparison\n")
    print(comparison)
    print("\n## Affordability (top match)\n")
    print(_fmt_affordability(next_steps["affordability"]))
    if export_result is not None:
        print("\n## Export\n")
        print(f"{export_result.format.upper()} written to {export_result.output_path}")
    print(f"\nTrace written to {trace_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="house-hunt",
        description="House hunting assistant — describe what you want, get ranked matches.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="search",
        choices=["search", "demo", "serve"],
        help=(
            "'search' (default) starts an interactive session; "
            "'demo' runs a fixed example; "
            "'serve' starts the optional MCP server"
        ),
    )
    parser.add_argument(
        "--export-path",
        help="Write demo results to a CSV or HTML file. Currently supported with the demo command.",
    )
    args = parser.parse_args()
    if args.command == "demo":
        run_demo(export_path=args.export_path)
    elif args.command == "serve":
        from src.ui.mcp_server import mcp
        mcp.run()
    else:
        run_interactive()


if __name__ == "__main__":
    main()
