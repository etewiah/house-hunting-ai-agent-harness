from __future__ import annotations

from html import escape
from pathlib import Path

from src.models.schemas import ExportOptions, ExportPayload, ExportResult


def export_html(
    payload: ExportPayload,
    options: ExportOptions,
    generated_at: str,
) -> ExportResult:
    output_path = Path(options.output_path or "house-hunt-report.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    listings = payload.ranked_listings[: options.max_listings]
    html = _render(payload, generated_at)
    output_path.write_text(html, encoding="utf-8")
    return ExportResult(
        format="html",
        output_path=str(output_path),
        file_size_bytes=output_path.stat().st_size,
        listing_count=len(listings),
        generated_at=generated_at,
        warnings=_warnings(payload),
    )


def _render(payload: ExportPayload, generated_at: str) -> str:
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

    listing_items = "\n".join(_render_listing(index, item) for index, item in enumerate(payload.ranked_listings, 1))
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
    <section>
      <h2>Ranked Listings</h2>
      {listing_items or '<p>No listings exported.</p>'}
    </section>
    <footer>
      <p>This report is an AI-assisted research aid. It is not mortgage, legal, survey,
      inspection, or valuation advice. Verify important details independently.</p>
    </footer>
  </main>
</body>
</html>
"""


def _render_listing(index: int, item) -> str:
    listing = item.listing
    commute = "unknown" if listing.commute_minutes is None else f"{listing.commute_minutes} minutes"
    matched = escape(", ".join(item.matched) or "None")
    missed = escape(", ".join(item.missed) or "None")
    warnings = escape(", ".join(item.warnings) or "None")
    extraction_quality = ""
    commute_meta = ""
    if listing.external_refs:
        quality = listing.external_refs.get("extraction_quality_score")
        parser = listing.external_refs.get("extraction_parser")
        commute_estimation = listing.external_refs.get("commute_estimation")
        if quality is not None or parser is not None:
            quality_text = "unknown" if quality is None else f"{quality}/100"
            parser_text = "unknown" if parser is None else escape(str(parser))
            extraction_quality = f"<p><strong>Extraction:</strong> quality {quality_text} | parser {parser_text}</p>"
        if isinstance(commute_estimation, dict):
            destination = escape(str(commute_estimation.get("destination", "unknown")))
            mode = escape(str(commute_estimation.get("mode", "unknown")))
            commute_meta = f"<p><strong>Commute:</strong> estimated toward {destination} via {mode}</p>"
    return f"""
      <article class="listing">
        <h3>{index}. {escape(listing.title)} ({item.score:.0f}/100)</h3>
        <p>{escape(listing.location)} | {listing.price} | {listing.bedrooms} bed |
        {listing.bathrooms} bath | commute {escape(commute)}</p>
        <p><strong>Matched:</strong> {matched}</p>
        <p><strong>Missed:</strong> {missed}</p>
        <p><strong>Warnings:</strong> {warnings}</p>
        {commute_meta}
        {extraction_quality}
        <p><a href="{escape(listing.source_url)}">Source listing</a></p>
      </article>
    """


def _warnings(payload: ExportPayload) -> list[str]:
    if payload.buyer_profile is not None:
        return ["Export includes buyer budget and preference context."]
    return []
