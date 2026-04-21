import argparse
from pprint import pprint
from src.app import build_app

DEFAULT_BRIEF = (
    "I want a 3-bed within 45 minutes of King's Cross, budget £700k, "
    "walkable area, quiet street, decent garden."
)


def run_demo() -> None:
    app = build_app()
    profile = app.intake(DEFAULT_BRIEF)
    ranked = app.triage(limit=3)
    explanations = app.explain_top_matches()
    comparison = app.compare_top(count=3)
    next_steps = app.prep_next_steps()
    trace_path = app.tracer.flush("demo")

    print("\n## Buyer Profile")
    pprint(profile)
    print("\n## Ranked Listings")
    pprint(ranked)
    print("\n## Explanations")
    for explanation in explanations:
        print(f"- {explanation}")
    print("\n## Comparison")
    print(comparison)
    print("\n## Next Steps")
    pprint(next_steps)
    print(f"\nTrace written to {trace_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="demo", choices=["demo"])
    args = parser.parse_args()
    if args.command == "demo":
        run_demo()


if __name__ == "__main__":
    main()

