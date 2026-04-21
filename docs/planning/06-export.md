# 06 - Session Export

## Purpose

The harness should make house-hunting work shareable. A buyer may want to send a shortlist
to a partner, mortgage broker, solicitor, relocation adviser, or simply review it later
without rerunning the tool.

Exports should be format- and platform-agnostic. HomesToCompare can be a strong export
target when configured, but the core harness should also support plain files that work
anywhere.

## Harness Contract

Export should accept:

- Buyer profile or session.
- Ranked listings or shortlist.
- Optional generated outputs: comparison narrative, affordability estimates, questions,
  area data, commute estimates, image analysis, notes.
- Format options.
- Privacy and inclusion flags.

It should return:

- Format.
- Output path or platform URL.
- Listing count.
- Generated timestamp.
- File size where relevant.
- Warnings about omitted data, missing dependencies, privacy, or platform failures.

## Formats

Recommended formats:

- `html`: self-contained local report for easy sharing and offline review.
- `csv`: spreadsheet-friendly shortlist for buyers who want their own tracker.
- `pdf`: fixed report for email or professional handoff.
- `platform`: push to a configured platform and return a shareable URL.

The default should be deployment-aware:

- If a platform connector is configured and the user requested link sharing, use platform.
- Otherwise prefer HTML for human review.
- CSV remains the simplest dependency-free structured export.

## LLM Responsibilities

The LLM should:

- Choose an export format that matches the user's goal.
- Warn when exports include sensitive buyer preferences or financial assumptions.
- Avoid including unsupported claims in generated reports.
- Preserve provenance and advisory labels.
- Summarize omitted data when an export format cannot represent everything cleanly.

## Suggested Data Shape

```python
@dataclass
class ExportOptions:
    format: str
    output_path: str | None = None
    include_images: bool = True
    include_affordability: bool = True
    include_area_data: bool = True
    include_image_analysis: bool = True
    include_notes: bool = True
    max_listings: int = 5


@dataclass(frozen=True)
class ExportResult:
    format: str
    listing_count: int
    generated_at: str
    output_path: str | None = None
    share_url: str | None = None
    machine_readable_url: str | None = None
    file_size_bytes: int | None = None
    warnings: list[str] = field(default_factory=list)
```

An internal `ExportPayload` can assemble data from session state, but it should remain
provider-neutral.

## Export Adapter Pattern

```python
class Exporter(Protocol):
    format: str

    def export(self, payload: ExportPayload, options: ExportOptions) -> ExportResult:
        ...
```

Recommended exporters:

- CSV exporter using Python stdlib.
- HTML exporter using a template renderer or simple string templates.
- PDF exporter behind an optional dependency.
- Platform exporter using a configured connector.

## Platform Integration

Platform export should be optional and isolated:

- Convert the normalized export payload into the platform API shape.
- Preserve backward compatibility with simple listings-only comparison creation.
- Store returned URLs in the export result and session external refs.
- Fail gracefully when credentials or platform APIs are unavailable.

HomesToCompare comparison pages are one implementation of the platform exporter.

## Implementation Guidance

- Start with CSV or HTML; both provide immediate value with low implementation risk.
- Keep PDF optional because dependencies and layout requirements vary by environment.
- Include a short disclaimer in human-readable exports.
- Include provenance fields in CSV where possible.
- Avoid strict CSV column-count tests unless the column contract is intentionally frozen.
- Provide `--no-images` or equivalent for privacy and file-size control.

## Testing Focus

- Export works from current session state and from a saved session.
- CSV includes required columns and escapes values correctly.
- HTML is self-contained when requested.
- Missing optional dependencies produce clear errors.
- Platform export failure does not break local export.
- Privacy warning appears when buyer budget or notes are included.

## Open Questions

- Should platform export be the default whenever configured, or require explicit consent?
- Should exported files include full notes by default?
- How long should platform share URLs remain accessible?
