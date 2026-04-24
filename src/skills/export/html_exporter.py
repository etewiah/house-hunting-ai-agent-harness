from __future__ import annotations

from html import escape
from pathlib import Path

from src.harness.policies import advice_boundary_notice
from src.models.schemas import ExportOptions, ExportPayload, ExportResult


def export_html(
    payload: ExportPayload,
    options: ExportOptions,
    generated_at: str,
) -> ExportResult:
    output_path = Path(options.output_path or "house-hunt-report.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    listings = payload.ranked_listings[: options.max_listings]
    html = _render(payload, generated_at, listings, include_area_data=options.include_area_data)
    output_path.write_text(html, encoding="utf-8")
    return ExportResult(
        format="html",
        output_path=str(output_path),
        file_size_bytes=output_path.stat().st_size,
        listing_count=len(listings),
        generated_at=generated_at,
        warnings=_warnings(payload),
    )


def _render(payload: ExportPayload, generated_at: str, listings, include_area_data: bool = True) -> str:
    profile = payload.buyer_profile
    profile_html = ""
    if profile is not None:
        profile_html = f"""
        <section>
          <h2>Buyer Profile</h2>
          <dl>
            <dt>Location</dt><dd>{escape(profile.location_query)}</dd>
            <dt>Budget</dt><dd>{profile.max_budget}</dd>
            <dt>Bedrooms</dt><dd>{profile.min_bedrooms}+</dd>
            <dt>Must-haves</dt><dd>{escape(', '.join(profile.must_haves) or 'None supplied')}</dd>
          </dl>
        </section>
        """

    acquisition_html = ""
    acquisition = payload.generated_outputs.get("acquisition_summary") if payload.generated_outputs else None
    if isinstance(acquisition, dict) and acquisition:
        exclusion = acquisition.get("exclusion_reasons")
        exclusion_html = ""
        if isinstance(exclusion, dict):
            exclusion_html = (
                "<p><strong>Excluded:</strong> "
                f"location filter {escape(str(exclusion.get('location_filter', 0)))}, "
                f"requirement filters {escape(str(exclusion.get('requirement_filters', 0)))}, "
                f"rank limit {escape(str(exclusion.get('rank_limit', 0)))}</p>"
            )
        acquisition_html = f"""
        <section>
          <h2>Acquisition Summary</h2>
          <p><strong>Candidates:</strong> {escape(str(acquisition.get('candidate_count', 0)))}</p>
          <p><strong>Location matched:</strong> {escape(str(acquisition.get('located_count', 0)))}</p>
          <p><strong>After requirement filters:</strong> {escape(str(acquisition.get('filtered_count', 0)))}</p>
          <p><strong>Ranked:</strong> {escape(str(acquisition.get('ranked_count', 0)))}</p>
          {exclusion_html}
        </section>
        """

    area_rollup_html = ""
    rollup = payload.generated_outputs.get("area_evidence_rollup") if payload.generated_outputs else None
    if isinstance(rollup, dict):
        by_source = rollup.get("evidence_by_source")
        by_source_text = "none"
        if isinstance(by_source, dict) and by_source:
            by_source_text = ", ".join([f"{escape(str(k))}={escape(str(v))}" for k, v in sorted(by_source.items())])
        confidence_band = escape(str(rollup.get("confidence_band", "unknown")))
        confidence_reason = escape(str(rollup.get("confidence_reason", "")))
        area_rollup_html = f"""
        <section>
          <h2>Area Evidence Rollup</h2>
          <p><strong>Listings with area context:</strong> {escape(str(rollup.get('listings_with_area_context', 0)))}</p>
          <p><strong>Total evidence items:</strong> {escape(str(rollup.get('total_evidence_items', 0)))}</p>
          <p><strong>Total area warnings:</strong> {escape(str(rollup.get('total_area_warnings', 0)))}</p>
          <p><strong>Confidence band:</strong> {confidence_band}</p>
          <p><strong>Confidence note:</strong> {confidence_reason}</p>
          <p><strong>By source:</strong> {by_source_text}</p>
        </section>
        """

    comparison_html = ""
    comparison = payload.generated_outputs.get("structured_comparison") if payload.generated_outputs else None
    if isinstance(comparison, dict) and comparison:
        trade_offs = comparison.get("trade_offs")
        deal_breakers = comparison.get("deal_breakers")
        verification_items = comparison.get("verification_items")
        trade_offs_html = _render_list(trade_offs if isinstance(trade_offs, list) else [])
        deal_breakers_html = _render_list(deal_breakers if isinstance(deal_breakers, list) else [])
        verification_html = _render_verification_items(
            verification_items if isinstance(verification_items, list) else []
        )
        comparison_html = f"""
        <section>
          <h2>Recommendation And Trade-Offs</h2>
          <p><strong>Recommendation:</strong> {escape(str(comparison.get('recommendation_summary', 'No recommendation available.')))}</p>
          <p><strong>Confidence:</strong> {escape(str(comparison.get('confidence', 'unknown')))}</p>
          <p><strong>Close-call score:</strong> {escape(str(comparison.get('close_call_score', 'unknown')))}</p>
          <h3>Visible trade-offs</h3>
          {trade_offs_html}
          <h3>Possible deal-breakers</h3>
          {deal_breakers_html}
          <h3>What to verify next</h3>
          {verification_html}
        </section>
        """

    listing_items = "\n".join(
      _render_listing(index, item, include_area_data=include_area_data)
      for index, item in enumerate(listings, 1)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>House Hunting Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.45; color: #202124; }}
    main {{ max-width: 900px; margin: 0 auto; }}
    h1, h2 {{ line-height: 1.2; }}
    .listing {{ border-top: 1px solid #ddd; padding: 1rem 0; }}
    .meta, footer {{ color: #5f6368; }}
    dt {{ font-weight: 700; float: left; min-width: 8rem; }}
    dd {{ margin: 0 0 .4rem 8.5rem; }}
  </style>
</head>
<body>
  <main>
    <h1>House Hunting Report</h1>
    <p class="meta">Generated {escape(generated_at)}</p>
    {profile_html}
    {acquisition_html}
    {area_rollup_html}
    {comparison_html}
    <section>
      <h2>Ranked Listings</h2>
      {listing_items or '<p>No listings exported.</p>'}
    </section>
    <footer>
      <p>This report is an AI-assisted research aid. {escape(advice_boundary_notice())}
      Verify important details independently.</p>
    </footer>
  </main>
</body>
</html>
"""


def _render_list(items: list[object]) -> str:
    if not items:
        return "<p>None identified from the current evidence.</p>"
    return "<ul>" + "".join(f"<li>{escape(str(item))}</li>" for item in items) + "</ul>"


def _render_verification_items(items: list[object]) -> str:
    if not items:
        return "<p>No specific verification items were generated.</p>"
    parts: list[str] = []
    for raw in items:
        if not isinstance(raw, dict):
            parts.append(f"<li>{escape(str(raw))}</li>")
            continue
        priority = escape(str(raw.get("priority", "medium")))
        listing_id = escape(str(raw.get("listing_id") or "all listings"))
        question = escape(str(raw.get("question", "")))
        reason = escape(str(raw.get("reason", "")))
        source = escape(str(raw.get("source", "inferred")))
        parts.append(
            f"<li><strong>{priority}</strong> | {listing_id}: {question} "
            f"<small>Reason: {reason} Source: {source}</small></li>"
        )
    return "<ul>" + "".join(parts) + "</ul>"


def _render_listing(index: int, item, include_area_data: bool = True) -> str:
    listing = item.listing
    commute = "unknown" if listing.commute_minutes is None else f"{listing.commute_minutes} minutes"
    matched = escape(", ".join(item.matched) or "None")
    missed = escape(", ".join(item.missed) or "None")
    warnings = escape(", ".join(item.warnings) or "None")
    extraction_quality = ""
    commute_meta = ""
    area_meta = ""
    if listing.external_refs:
        quality = listing.external_refs.get("extraction_quality_score")
        parser = listing.external_refs.get("extraction_parser")
        commute_estimation = listing.external_refs.get("commute_estimation")
        diagnostics = listing.external_refs.get("extraction_diagnostics")
        missing_fields = diagnostics.get("missingFields", []) if isinstance(diagnostics, dict) else []
        diag_warnings = diagnostics.get("warnings", []) if isinstance(diagnostics, dict) else []
        if quality is not None or parser is not None:
            quality_text = "unknown" if quality is None else f"{quality}/100"
            parser_text = "unknown" if parser is None else escape(str(parser))
            missing_text = (
                f" | unconfirmed: {escape(', '.join(missing_fields))}"
                if missing_fields else ""
            )
            warn_text = (
                f"<br><small>Extraction notes: {escape('; '.join(diag_warnings))}</small>"
                if diag_warnings else ""
            )
            extraction_quality = (
                f"<p><strong>Extraction:</strong> quality {quality_text} | parser {parser_text}"
                f"{missing_text}{warn_text}</p>"
            )
        if isinstance(commute_estimation, dict):
            destination = escape(str(commute_estimation.get("destination", "unknown")))
            mode = escape(str(commute_estimation.get("mode", "unknown")))
            source = commute_estimation.get("source", "")
            inferred_note = " (inferred from brief)" if source == "estimated" else ""
            commute_meta = f"<p><strong>Commute:</strong> estimated toward {destination} via {mode}{inferred_note}</p>"
    if include_area_data and listing.area_data is not None and listing.area_data.evidence:
        top_evidence = listing.area_data.evidence[:3]
        evidence_parts = [
            f"{escape(item.category)} ({escape(item.source)}): {escape(item.summary)}"
            for item in top_evidence
        ]
        area_meta = f"<p><strong>Area context:</strong> {' | '.join(evidence_parts)}</p>"
    return f"""
      <article class="listing">
        <h3>{index}. {escape(listing.title)} ({item.score:.0f}/100)</h3>
        <p>{escape(listing.location)} | {listing.price} | {listing.bedrooms} bed |
        {listing.bathrooms} bath | commute {escape(commute)}</p>
        <p><strong>Matched:</strong> {matched}</p>
        <p><strong>Missed:</strong> {missed}</p>
        <p><strong>Warnings:</strong> {warnings}</p>
        {commute_meta}
        {area_meta}
        {extraction_quality}
        <p><a href="{escape(listing.source_url)}">Source listing</a></p>
      </article>
    """


def _warnings(payload: ExportPayload) -> list[str]:
  warnings: list[str] = []
  if payload.buyer_profile is not None:
    warnings.append("Export includes buyer budget and preference context.")
  rollup = payload.generated_outputs.get("area_evidence_rollup") if payload.generated_outputs else None
  if isinstance(rollup, dict):
    total = int(rollup.get("total_evidence_items", 0) or 0)
    listings = int(rollup.get("listings_with_area_context", 0) or 0)
    confidence_band = str(rollup.get("confidence_band", "unknown"))
    by_source = rollup.get("evidence_by_source")
    by_source_text = ""
    if isinstance(by_source, dict) and by_source:
      by_source_text = ", ".join([f"{k}={v}" for k, v in sorted(by_source.items())])
    warning = f"Area evidence rollup: {total} evidence items across {listings} listings [confidence={confidence_band}]"
    if by_source_text:
      warning = f"{warning} ({by_source_text})."
    else:
      warning = f"{warning}."
    warnings.append(warning)
  return warnings
