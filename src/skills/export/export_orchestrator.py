from __future__ import annotations

from datetime import datetime, timezone

from src.models.schemas import ExportOptions, ExportPayload, ExportResult
from src.skills.export.csv_exporter import export_csv
from src.skills.export.html_exporter import export_html


class ExportOrchestrator:
    def export(self, payload: ExportPayload, options: ExportOptions) -> ExportResult:
        generated_at = datetime.now(timezone.utc).isoformat()
        if options.format == "csv":
            return export_csv(payload, options, generated_at=generated_at)
        if options.format == "html":
            return export_html(payload, options, generated_at=generated_at)
        return ExportResult(
            format=options.format,
            listing_count=0,
            generated_at=generated_at,
            warnings=[f"Unsupported export format: {options.format}"],
        )
