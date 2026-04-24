"""
Trace viewer for house-hunt session traces.

Usage:
    uv run house-hunt trace                  # most recent trace in .traces/
    uv run house-hunt trace session.json     # specific file
    uv run house-hunt trace --list           # list available traces
    uv run house-hunt trace --json           # dump raw JSON of most recent trace
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TRACES_DIR = Path(".traces")
_DIVIDER = "─" * 60
_THIN = "·" * 60


def _find_traces() -> list[Path]:
    if not _TRACES_DIR.exists():
        return []
    return sorted(_TRACES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def _load(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path} is not a valid trace file (expected a JSON array)")
    return raw


def _parse_ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _relative(start: datetime, ts: datetime) -> str:
    delta = (ts - start).total_seconds()
    if delta < 0.001:
        return "+0.000s"
    return f"+{delta:.3f}s"


# ---------------------------------------------------------------------------
# Per-event renderers
# ---------------------------------------------------------------------------

def _render_intake_profile(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [repr(payload)]
    lines = [
        f"  Location:      {payload.get('location_query', '?')}",
        f"  Budget:        £{payload.get('max_budget', 0):,}",
        f"  Bedrooms:      {payload.get('min_bedrooms', '?')}+",
    ]
    if payload.get("max_commute_minutes"):
        lines.append(f"  Commute:       {payload['max_commute_minutes']} mins max")
    if payload.get("must_haves"):
        lines.append(f"  Must-haves:    {', '.join(payload['must_haves'])}")
    if payload.get("nice_to_haves"):
        lines.append(f"  Nice-to-haves: {', '.join(payload['nice_to_haves'])}")
    return lines


def _render_ranked_listings(payload: Any) -> list[str]:
    if not isinstance(payload, (list, dict)):
        return [repr(payload)]
    items = payload.get("items", payload) if isinstance(payload, dict) else payload
    warnings = payload.get("warnings", []) if isinstance(payload, dict) else []
    count = payload.get("count", len(items)) if isinstance(payload, dict) else len(items)
    lines = [f"  {count} listing(s) ranked"]
    for i, item in enumerate(items[:5], 1):
        if not isinstance(item, dict):
            continue
        listing = item.get("listing", {})
        score = item.get("score", 0)
        title = listing.get("title", "?")
        price = listing.get("price", 0)
        location = listing.get("location", "?")
        matched = item.get("matched", [])
        missed = item.get("missed", [])
        warn = item.get("warnings", [])
        commute = listing.get("commute_minutes")
        commute_str = "?" if commute is None else f"{commute} min"
        lines.append(f"  {i}. {title}  [{score:.0f}/100]  £{price:,}  {location}  {commute_str} commute")
        if matched:
            lines.append(f"     + {', '.join(matched)}")
        if missed:
            lines.append(f"     - Missed: {', '.join(missed)}")
        if warn:
            lines.append(f"     ! {', '.join(warn)}")
        ext = listing.get("external_refs") or {}
        if ext.get("extraction_quality_score") is not None:
            parser = ext.get("extraction_parser", "?")
            q = ext.get("extraction_quality_score")
            missing = ext.get("extraction_diagnostics", {}).get("missingFields", []) if isinstance(ext.get("extraction_diagnostics"), dict) else []
            missing_str = f"  unconfirmed: {', '.join(missing)}" if missing else ""
            lines.append(f"     ~ extraction: {parser} quality {q}/100{missing_str}")
    if len(items) > 5:
        lines.append(f"  … and {len(items) - 5} more")
    for w in warnings:
        lines.append(f"  ! {w}")
    return lines


def _render_acquisition_summary(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [repr(payload)]
    lines = [
        f"  Candidates:   {payload.get('candidate_count', 0)}",
        f"  Located:      {payload.get('located_count', 0)}",
        f"  After filters:{payload.get('filtered_count', 0)}",
        f"  Ranked:       {payload.get('ranked_count', 0)}",
    ]
    exc = payload.get("exclusion_reasons")
    if isinstance(exc, dict):
        parts = [f"location={exc.get('location_filter', 0)}",
                 f"requirements={exc.get('requirement_filters', 0)}",
                 f"rank_limit={exc.get('rank_limit', 0)}"]
        lines.append(f"  Excluded:     {', '.join(parts)}")
    return lines


def _render_explanations(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return [repr(payload)]
    lines = []
    for exp in payload[:3]:
        lines.append(f"  {exp}")
    if len(payload) > 3:
        lines.append(f"  … {len(payload) - 3} more")
    return lines


def _render_guardrails(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [repr(payload)]
    scope = payload.get("scope", "")
    results = payload.get("results", [])
    if results:
        all_passed = all(r.get("passed", True) for r in results if isinstance(r, dict))
        violations = [v for r in results if isinstance(r, dict) for v in r.get("violations", [])]
        warnings = [w for r in results if isinstance(r, dict) for w in r.get("warnings", [])]
        scope_str = f"  {scope}" if scope else ""
        lines = [f"  Passed: {all_passed}{scope_str}  ({len(results)} check(s))"]
        for v in violations[:3]:
            lines.append(f"  ! violation: {v}")
        for w in warnings[:3]:
            lines.append(f"  ~ warning: {w}")
        return lines
    passed = payload.get("passed", payload.get("ok", "?"))
    lines = [f"  Passed: {passed}"]
    for v in payload.get("violations", [])[:3]:
        lines.append(f"  ! {v}")
    return lines


def _render_comparison(payload: Any) -> list[str]:
    text = payload if isinstance(payload, str) else payload.get("text", repr(payload)) if isinstance(payload, dict) else repr(payload)
    snippet = str(text).strip()
    line_parts = snippet.split("\n")[:6]
    return [f"  {ln}" for ln in line_parts] + (["  …"] if len(str(text).split("\n")) > 6 else [])


def _render_next_steps(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [repr(payload)]
    lines = []
    aff = payload.get("affordability")
    if isinstance(aff, dict):
        lines.append(f"  Affordability: deposit £{aff.get('deposit', 0):,}  loan £{aff.get('loan_amount', 0):,}  ~£{aff.get('monthly_payment', 0):,}/mo")
    tq = payload.get("tour_questions", [])
    if tq:
        lines.append(f"  Tour questions: {len(tq)} generated")
        lines.append(f"  e.g. {tq[0]}")
    ob = payload.get("offer_brief", "")
    if ob:
        snippet = str(ob)[:120].strip()
        lines.append(f"  Offer brief: {snippet}{'…' if len(str(ob)) > 120 else ''}")
    return lines


def _render_export(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [repr(payload)]
    fmt = payload.get("format", "?")
    path = payload.get("output_path", "?")
    count = payload.get("listing_count", "?")
    size = payload.get("file_size_bytes")
    size_str = f"  ({size:,} bytes)" if size else ""
    return [f"  {fmt.upper()} export: {path}  [{count} listings]{size_str}"]


def _render_pipeline_status(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [repr(payload)]
    history = payload.get("history", [])
    lines = []
    for entry in history[-3:]:
        if not isinstance(entry, dict):
            continue
        stage = entry.get("stage", "?")
        msg = entry.get("message", "")
        metrics = entry.get("metrics")
        metric_str = ""
        if isinstance(metrics, dict) and metrics:
            metric_str = "  (" + ", ".join(f"{k}={v}" for k, v in metrics.items()) + ")"
        lines.append(f"  {stage}: {msg}{metric_str}")
    return lines


_RENDERERS: dict[str, Any] = {
    "intake.profile_created": _render_intake_profile,
    "triage.ranked_listings": _render_ranked_listings,
    "triage.acquisition_summary": _render_acquisition_summary,
    "triage.explanations": _render_explanations,
    "guardrails.checked": _render_guardrails,
    "comparison.summary": _render_comparison,
    "comparison.created": _render_comparison,
    "next_steps.prepared": _render_next_steps,
    "export.created": _render_export,
    "pipeline.status": _render_pipeline_status,
}

_LABELS: dict[str, str] = {
    "intake.profile_created":    "INTAKE        Buyer brief parsed",
    "triage.ranked_listings":    "TRIAGE        Listings ranked",
    "triage.acquisition_summary":"TRIAGE        Acquisition summary",
    "triage.explanations":       "TRIAGE        Explanations generated",
    "guardrails.checked":        "GUARDRAILS    Output checked",
    "comparison.summary":        "COMPARISON    Summary produced",
    "comparison.created":        "COMPARISON    Created",
    "next_steps.prepared":       "NEXT STEPS    Prepared",
    "export.created":            "EXPORT        File written",
    "pipeline.status":           "PIPELINE      Status update",
}


# ---------------------------------------------------------------------------
# Main rendering
# ---------------------------------------------------------------------------

def render_trace(events: list[dict[str, Any]], path: Path) -> str:
    if not events:
        return f"  (empty trace: {path})"

    lines: list[str] = []

    # Session header
    first_ts = _parse_ts(events[0]["at"])
    last_ts = _parse_ts(events[-1]["at"])
    duration = (last_ts - first_ts).total_seconds()

    lines.append(_DIVIDER)
    lines.append(f"  Trace: {path}")
    lines.append(f"  Start: {first_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"  Duration: {duration:.3f}s   Events: {len(events)}")
    lines.append(_DIVIDER)

    # Events
    for event in events:
        name = event.get("name", "unknown")
        ts = _parse_ts(event["at"])
        rel = _relative(first_ts, ts)
        label = _LABELS.get(name, f"EVENT         {name}")
        renderer = _RENDERERS.get(name)

        lines.append(f"\n{rel}  {label}")

        if renderer is not None:
            body = renderer(event.get("payload"))
        else:
            body = [f"  {json.dumps(event.get('payload'), indent=2)[:200]}"]

        lines.extend(body)

    # Session summary
    lines.append(f"\n{_DIVIDER}")
    stage_names = [e.get("name", "") for e in events]
    completed = []
    if "intake.profile_created" in stage_names:
        completed.append("intake")
    if "triage.ranked_listings" in stage_names:
        completed.append("ranking")
    if "triage.explanations" in stage_names:
        completed.append("explanations")
    if any(n.startswith("comparison") for n in stage_names):
        completed.append("comparison")
    if "next_steps.prepared" in stage_names:
        completed.append("next_steps")
    if "export.created" in stage_names:
        completed.append("export")
    if completed:
        lines.append(f"  Stages completed: {', '.join(completed)}")
    else:
        lines.append("  No pipeline stages recorded")
    lines.append(_DIVIDER)

    return "\n".join(lines)


def render_list(paths: list[Path]) -> str:
    if not paths:
        return "  No trace files found in .traces/"
    lines = ["  Available traces (newest first):\n"]
    for i, p in enumerate(paths):
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        size = p.stat().st_size
        lines.append(f"  {i + 1:2}. {p.name:<40} {mtime.strftime('%Y-%m-%d %H:%M')}  {size:,} B")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(path_arg: str | None = None, list_only: bool = False, raw_json: bool = False) -> None:
    if list_only:
        traces = _find_traces()
        print(render_list(traces))
        return

    if path_arg:
        target = Path(path_arg)
        if not target.exists():
            # Try relative to .traces/
            alt = _TRACES_DIR / path_arg
            if alt.exists():
                target = alt
            else:
                print(f"  Error: trace file not found: {path_arg}")
                return
    else:
        traces = _find_traces()
        if not traces:
            print("  No trace files found in .traces/")
            print("  Run a browser-assisted or provider-backed harness workflow to generate one.")
            return
        target = traces[0]

    try:
        events = _load(target)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  Error loading trace: {e}")
        return

    if raw_json:
        print(json.dumps(events, indent=2))
        return

    print(render_trace(events, target))
