from __future__ import annotations

import csv
from pathlib import Path

from src.models.schemas import ExportOptions, ExportPayload, ExportResult, RankedListing

REQUIRED_COLUMNS = [
    "rank",
    "score",
    "title",
    "price",
    "bedrooms",
    "bathrooms",
    "location",
    "commute_minutes",
    "matched_features",
    "missed_features",
    "warnings",
    "commute_estimated",
    "commute_destination",
    "commute_mode",
    "extraction_quality_score",
    "extraction_parser",
    "area_evidence_count",
    "area_top_categories",
    "area_warning_count",
    "source_url",
]


def export_csv(
    payload: ExportPayload,
    options: ExportOptions,
    generated_at: str,
) -> ExportResult:
    output_path = Path(options.output_path or "house-hunt-shortlist.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = _rows(payload.ranked_listings[: options.max_listings], include_area_data=options.include_area_data)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return ExportResult(
        format="csv",
        output_path=str(output_path),
        file_size_bytes=output_path.stat().st_size,
        listing_count=len(rows),
        generated_at=generated_at,
        warnings=_warnings(payload),
    )


def _rows(ranked_listings: list[RankedListing], include_area_data: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, item in enumerate(ranked_listings, 1):
        listing = item.listing
        commute_estimation = listing.external_refs.get("commute_estimation") if listing.external_refs else None
        extraction_quality = listing.external_refs.get("extraction_quality_score") if listing.external_refs else None
        extraction_parser = listing.external_refs.get("extraction_parser") if listing.external_refs else None
        area_evidence_count = 0
        area_top_categories = ""
        area_warning_count = 0
        if include_area_data and listing.area_data is not None:
            area_evidence_count = len(listing.area_data.evidence)
            area_top_categories = ";".join([item.category for item in listing.area_data.evidence[:3]])
            area_warning_count = len(listing.area_data.warnings)
        rows.append(
            {
                "rank": index,
                "score": f"{item.score:.1f}",
                "title": listing.title,
                "price": listing.price,
                "bedrooms": listing.bedrooms,
                "bathrooms": listing.bathrooms,
                "location": listing.location,
                "commute_minutes": "" if listing.commute_minutes is None else listing.commute_minutes,
                "matched_features": ";".join(item.matched),
                "missed_features": ";".join(item.missed),
                "warnings": ";".join(item.warnings),
                "commute_estimated": "yes" if commute_estimation else "",
                "commute_destination": "" if not isinstance(commute_estimation, dict) else commute_estimation.get("destination", ""),
                "commute_mode": "" if not isinstance(commute_estimation, dict) else commute_estimation.get("mode", ""),
                "extraction_quality_score": "" if extraction_quality is None else extraction_quality,
                "extraction_parser": "" if extraction_parser is None else extraction_parser,
                "area_evidence_count": area_evidence_count if include_area_data else "",
                "area_top_categories": area_top_categories if include_area_data else "",
                "area_warning_count": area_warning_count if include_area_data else "",
                "source_url": listing.source_url,
            }
        )
    return rows


def _warnings(payload: ExportPayload) -> list[str]:
    warnings: list[str] = []
    if payload.buyer_profile is not None:
        warnings.append("Export includes buyer budget and preference context in session metadata.")
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
