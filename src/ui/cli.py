from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="house-hunt",
        description=(
            "House hunting harness utilities. Use repository skills or Python modules "
            "for buyer-brief workflows; use this command for MCP and trace utilities."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["serve", "trace"],
        help=(
            "'serve' starts the optional MCP server; "
            "'trace' inspects a saved session trace"
        ),
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
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        print(
            "\nStandalone interactive listing search has been removed because it cannot "
            "discover live listings without an external provider. For buyer-brief "
            "workflows, use the repo-local Codex skills or import src.app.build_app() "
            "with listings supplied by a provider or browser-assisted workflow."
        )
        return

    if args.command == "serve":
        from src.ui.mcp_server import mcp

        mcp.run()
        return

    from src.ui.trace_viewer import main as trace_main

    trace_main(path_arg=args.trace_path, list_only=args.list, raw_json=args.json)


if __name__ == "__main__":
    main()
