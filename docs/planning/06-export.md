# 06 — Session Export

## Goal

At the end of a house-hunting session the buyer has ranked listings, explanations,
a comparison narrative, affordability estimates, image analysis notes, area data,
and tour questions. Today all of this lives in the terminal and the trace file. Neither
is shareable.

A serious buyer at the point of booking viewings needs to be able to:

- **Share with a partner**: "Here are the top 3 — which ones do you want to see?"
- **Brief a mortgage broker**: "Here's my budget, top picks, and monthly payment estimates."
- **Share with a solicitor**: "These are the properties we're considering."
- **Work offline**: Review the shortlist on their phone without running the tool again.

This feature adds four export formats:

1. **H2C comparison page** (`--format h2c`): The primary sharing format. Pushes the
   comparison to HomesToCompare and returns a URL like
   `https://homestocompare.com/pc/XXXXX/overview`. The buyer can share this link. It
   works on any device, requires no special software, and the H2C page can be viewed
   by anyone.

2. **PDF** (`--format pdf`): A self-contained document with buyer profile, ranked
   listings, match explanations, comparison, affordability estimates, and tour
   questions. Suitable for email attachment. Branded plainly (no design assets
   required).

3. **HTML** (`--format html`): A self-contained single-file HTML export. No server
   required; opens in any browser. Includes all session data plus image thumbnails
   if available.

4. **CSV** (`--format csv`): A flat spreadsheet of the shortlist. Each row is a
   listing with key attributes as columns. Suitable for buyers who use a spreadsheet
   to track their search.

The H2C export is by far the most compelling — it is the only format that is
persistent, shareable by link, and viewable on mobile without downloading a file.
It should be the default when H2C credentials are configured.

---

## HomesToCompare Integration

H2C is the primary and most powerful export target. The existing
`HomesToCompareConnector.create_comparison(listings)` already creates a comparison
and returns a URL. This feature extends that:

1. **Full comparison push.** The existing API accepts `listings` only. The extended
   call includes: buyer profile, ranked scores, match/miss annotations, affordability
   estimates, comparison narrative (from Feature 02), image analysis flags (from
   Feature 05), and area data (from Feature 03). H2C stores all of this and surfaces
   it on the comparison page.

2. **Shareable URL.** `create_comparison` returns a `suid_code`. The shareable link
   is `https://homestocompare.com/pc/{suid_code}/overview`. The CLI prints this URL
   prominently. The MCP tool returns it in the response dict.

3. **For-the-AI URL.** The machine-readable companion URL
   `https://homestocompare.com/pc/{suid_code}/for-the-ai` allows a subsequent
   Claude Code session to pick up exactly where the last one left off — even without
   the local session file.

4. **Quest linkage.** If a persistent session (Feature 04) has an `h2c_quest_id`,
   the export links the comparison to the quest, so the quest page at
   `/mq/[quest_id]` includes a reference to this comparison.

This H2C integration means the export is not a dead end — it feeds back into the
persistence and enrichment pipeline.

---

## External APIs / Services

### PDF generation — WeasyPrint
- URL: https://weasyprint.org/
- Install: `pip install weasyprint`
- Cost: **Free** (open source, LGPL licence)
- Approach: Renders HTML to PDF using CSS Pager rules. No headless browser required.
- Notes: Requires system libraries (Pango, Cairo, GDK-PixBuf) on Linux/macOS.
  On macOS with Homebrew: `brew install pango`. May be complex to install.
- Best for: Production deployments where PDF quality matters.

### PDF generation — ReportLab (alternative to WeasyPrint)
- URL: https://www.reportlab.com/
- Install: `pip install reportlab`
- Cost: **Free** (BSD licence for the open-source version)
- Approach: Programmatic PDF construction (Platypus layout engine). No HTML needed.
  More portable than WeasyPrint (pure Python, no system dependencies).
- Best for: Simpler deployments or Windows compatibility.
- Notes: Output is less polished than WeasyPrint HTML-to-PDF but more reliable.

### PDF generation — fpdf2 (lightest option)
- URL: https://py-pdf.github.io/fpdf2/
- Install: `pip install fpdf2`
- Cost: **Free** (LGPL)
- No system dependencies. Pure Python. Limited CSS support but adequate for
  text-heavy documents.
- **Recommended for Phase 1** due to zero system dependencies.

### CSV — Python `csv` stdlib
- No dependency. Included in Python stdlib.

### HTML — Python `string.Template` or Jinja2
- Jinja2: `pip install jinja2`
- Cost: **Free** (BSD licence)
- Already possibly in the dependency tree. Used to render the self-contained HTML
  with inline CSS and base64-encoded images.

---

## Data Model Changes

### New `ExportOptions` dataclass

```python
@dataclass
class ExportOptions:
    format: str                          # "h2c" | "pdf" | "html" | "csv"
    output_path: str | None              # File path; None means stdout or auto-named
    include_images: bool = True          # Include image thumbnails (HTML/PDF only)
    include_affordability: bool = True
    include_tour_questions: bool = True
    include_area_data: bool = True
    include_image_analysis: bool = True
    include_comparison_narrative: bool = True
    max_listings: int = 5                # Cap to avoid overlong exports
    locale: str = "en-GB"               # For number/currency formatting
```

### New `ExportResult` dataclass

```python
@dataclass(frozen=True)
class ExportResult:
    format: str
    output_path: str | None              # File path written, or None for H2C
    h2c_comparison_url: str | None       # Populated for format="h2c"
    h2c_for_ai_url: str | None           # Companion machine-readable URL
    h2c_quest_url: str | None            # Quest URL if session has quest_id
    file_size_bytes: int | None          # Size of written file (PDF/HTML/CSV)
    listing_count: int
    generated_at: str                    # ISO 8601 datetime string
    warnings: list[str]                  # e.g. "Image analysis not available"
```

### New `ExportPayload` dataclass

Intermediate structure assembled from session state before rendering:

```python
@dataclass
class ExportPayload:
    buyer_profile: BuyerProfile
    ranked_listings: list[RankedListing]
    explanations: list[str]
    comparison_narrative: ComparisonNarrative | None
    affordability: dict[str, AffordabilityEstimate]   # keyed by listing_id
    tour_questions: dict[str, list[str]]              # keyed by listing_id
    area_data: dict[str, AreaData]                    # keyed by listing_id (Feature 03)
    image_analyses: dict[str, ImageAnalysis]          # keyed by listing_id (Feature 05)
    session_id: str | None
    h2c_quest_id: str | None
    generated_at: str
```

---

## New Files to Create

```
src/skills/export/__init__.py
```
Package init for the export skill.

```
src/skills/export/export_orchestrator.py
```
`ExportOrchestrator` class. Assembles `ExportPayload` from session state, then
dispatches to the appropriate renderer based on `ExportOptions.format`.

```
src/skills/export/h2c_exporter.py
```
H2C export renderer. Extends the comparison payload, calls
`HomesToCompareConnector.create_comparison`, returns the shareable URL.

```
src/skills/export/pdf_exporter.py
```
PDF renderer using fpdf2. Generates a multi-page document from `ExportPayload`.

```
src/skills/export/html_exporter.py
```
HTML renderer. Produces a single self-contained HTML file with inline CSS,
optionally embedding image thumbnails as base64.

```
src/skills/export/csv_exporter.py
```
CSV renderer. Flattens ranked listings to rows with columns for all key attributes.

```
src/skills/export/templates/report.html
```
Jinja2 HTML template for the HTML export. Includes inline CSS for clean
presentation without external dependencies.

```
tests/skills/export/test_export_orchestrator.py
```
Tests for payload assembly and format dispatch.

```
tests/skills/export/test_csv_exporter.py
```
Tests for CSV column structure and data fidelity.

```
tests/skills/export/test_html_exporter.py
```
Tests for HTML output validity and self-containment.

---

## Changes to Existing Files

### `src/harness/orchestrator.py`
- Add `export(options: ExportOptions) -> ExportResult` method.
  Assembles `ExportPayload` from `self.state`, calls `ExportOrchestrator.export()`.
- Called at the end of a session when `--export` is passed, or by the MCP tool.

### `src/ui/cli.py`
- Add `--export [h2c|pdf|html|csv]` argument (optional; if omitted, no export).
- Add `--export-path <path>` argument for file output path.
- After the session summary, if `--export` is set, call `app.export()` and display
  the result (file path or H2C URL).
- Default export format when `--export` is used without a value:
  - If `H2C_BASE_URL` and `H2C_HARNESS_KEY` are configured: `h2c`
  - Otherwise: `html`
- Add `export` as a top-level command: `house-hunt export --format pdf --from-session <id>`.
  This allows exporting a previously saved session without re-running the search.

### `src/connectors/homestocompare_connector.py`
- Extend `create_comparison` to accept the full `ExportPayload` (not just listings).
  Pass buyer profile, scores, narrative, and area data in the payload.
- The API should remain backward-compatible: `listings`-only calls still work.

### `src/app.py`
- Update `build_app()` to initialise the `ExportOrchestrator` if export is requested.

### `pyproject.toml`
- Add `fpdf2` as an optional dependency under `[project.optional-dependencies]`:
  ```toml
  [project.optional-dependencies]
  pdf = ["fpdf2>=2.7"]
  html = ["jinja2>=3.1"]
  export = ["fpdf2>=2.7", "jinja2>=3.1"]
  ```
- Install with: `uv pip install "house-hunt[export]"` or `uv pip install "house-hunt[pdf]"`

---

## MCP Server Tools

```python
@mcp.tool()
def export_session(
    brief: str,
    ranked_listings: list[dict],
    format: str = "h2c",
    output_path: str | None = None,
    include_affordability: bool = True,
    include_tour_questions: bool = True,
) -> dict:
    """Export a house-hunting session to a shareable format.

    Formats:
      "h2c"  — Push to HomesToCompare and return a shareable URL.
               Requires H2C_BASE_URL and H2C_HARNESS_KEY env vars.
               Returns {comparison_url, for_ai_url} in the result.
      "pdf"  — Write a PDF to output_path (or ./house-hunt-export.pdf).
               Requires: uv pip install "house-hunt[pdf]"
      "html" — Write a self-contained HTML file.
               Requires: uv pip install "house-hunt[html]"
      "csv"  — Write a CSV spreadsheet.
               No additional dependencies required.

    Args:
        brief: The buyer's original brief (used to reconstruct the profile).
        ranked_listings: List of ranked listing dicts from rank_listings tool.
        format: Export format (default "h2c").
        output_path: Where to write the file. Ignored for "h2c" format.
        include_affordability: Whether to include mortgage estimates. Default True.
        include_tour_questions: Whether to include viewing questions. Default True.

    Returns:
        {format, output_path, h2c_comparison_url, h2c_for_ai_url, listing_count,
         file_size_bytes, generated_at, warnings}
    """
    ...
```

```python
@mcp.tool()
def export_to_h2c(
    listings: list[dict],
    brief: str | None = None,
    narrative: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Push listings to HomesToCompare and return a shareable comparison URL.

    This is the fast path for H2C export when you don't need the full
    session export. For a full export with affordability, questions, and
    narrative, use export_session with format="h2c".

    Args:
        listings: Listing dicts (at minimum: id, title, price, bedrooms,
                  bathrooms, location, source_url).
        brief: Optional buyer brief. Used to label the comparison on H2C.
        narrative: Optional AI-generated comparison narrative (from compare_homes
                   with a brief). Included on the H2C page if provided.
        session_id: Optional session ID. Links the comparison to the buyer's quest.

    Returns:
        {comparison_url, for_ai_url, quest_url (if session linked), suid_code}

    Requires H2C_BASE_URL and H2C_HARNESS_KEY environment variables.
    """
    ...
```

```python
@mcp.tool()
def export_csv(
    brief: str,
    ranked_listings: list[dict],
    output_path: str | None = None,
) -> dict:
    """Export ranked listings to a CSV spreadsheet.

    Each row is a listing. Columns: rank, title, price, bedrooms, bathrooms,
    location, commute_minutes, score, matched_features, missed_features,
    warnings, source_url.

    Suitable for opening in Excel, Google Sheets, or Numbers.

    Args:
        brief: The buyer's brief (used to label the CSV header).
        ranked_listings: Output from rank_listings tool.
        output_path: File path. Defaults to ./house-hunt-shortlist.csv.

    Returns: {output_path, row_count, file_size_bytes}
    """
    ...
```

---

## CSV Column Specification

The CSV export should produce predictable, documented columns that work in Excel and
Google Sheets without any manipulation:

| Column | Source | Notes |
|--------|--------|-------|
| `rank` | `RankedListing` index | 1-based |
| `score` | `RankedListing.score` | 0–100 float, 1 decimal place |
| `title` | `Listing.title` | |
| `price` | `Listing.price` | Integer GBP, no currency symbol |
| `bedrooms` | `Listing.bedrooms` | |
| `bathrooms` | `Listing.bathrooms` | |
| `location` | `Listing.location` | |
| `postcode` | `Listing.postcode` | May be empty |
| `commute_minutes` | `Listing.commute_minutes` | Empty if None |
| `commute_source` | `Listing.commute_source` | "estimated" or "missing" |
| `matched_features` | `RankedListing.matched` | Semicolon-separated |
| `missed_features` | `RankedListing.missed` | Semicolon-separated |
| `warnings` | `RankedListing.warnings` + image flags | Semicolon-separated |
| `monthly_payment_est` | `AffordabilityEstimate.monthly_payment` | Advisory |
| `deposit_required` | `AffordabilityEstimate.deposit` | |
| `source_url` | `Listing.source_url` | |
| `h2c_comparison_url` | From session or H2C export | May be empty |
| `export_date` | Generated at export time | ISO date |

---

## PDF Content Structure

Pages in the generated PDF:

```
Page 1 — Title + Buyer Profile
  "House Hunting Report — [date]"
  Profile: location, budget, bedrooms, must-haves, commute

Page 2–N — Ranked Listings (one listing per half-page or full page)
  For each listing:
    Title, location, price, beds/baths, commute
    Score badge (e.g. "87/100")
    Matched features (green)
    Missed features (red)
    Warnings (amber)
    Explanation paragraph
    Affordability estimate (if included)
    Tour questions (if included)

Page N+1 — Comparison
  Either comparison table or narrative (if available)

Last page — Disclaimer
  "This report is an AI-assisted research aid. It is not mortgage, legal,
  survey, or valuation advice. All estimates are provisional."
```

---

## Implementation Phases

### Phase 1 — CSV export
**Deliverable:** `house-hunt export --format csv` produces a working spreadsheet.

- Implement `src/skills/export/csv_exporter.py`.
- Implement `ExportPayload` and `ExportResult` dataclasses.
- Implement `ExportOrchestrator` (CSV path only).
- Add `--export csv` to CLI.
- Add `export_csv` MCP tool.
- Unit tests for column structure and data types.

### Phase 2 — H2C export
**Deliverable:** `house-hunt export --format h2c` returns a shareable URL.

- Implement `src/skills/export/h2c_exporter.py`.
- Extend `HomesToCompareConnector.create_comparison` to accept the full payload.
- Add `export_to_h2c` and `export_session(format="h2c")` MCP tools.
- CLI: print H2C URL prominently at session end.
- Integration test: create comparison, verify URL is accessible.

### Phase 3 — HTML export
**Deliverable:** `house-hunt export --format html` writes a self-contained file.

- Implement `src/skills/export/html_exporter.py` and `templates/report.html`.
- Self-contained: inline CSS, no external resources, images as base64 if available.
- Add `--export html` to CLI.
- Test: validate HTML structure, check all listing data is present.

### Phase 4 — PDF export
**Deliverable:** `house-hunt export --format pdf` writes a PDF file.

- Implement `src/skills/export/pdf_exporter.py` using `fpdf2`.
- Multi-page document with the structure defined above.
- `pyproject.toml` optional dependency `[export]` group.
- Graceful error if `fpdf2` is not installed: clear message with install command.
- Integration test: generate PDF, check file size > 5KB, check is valid PDF.

---

## Testing Plan

### Unit tests

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_csv_column_count` | 3 ranked listings | CSV has exactly 18 data columns |
| `test_csv_price_no_symbol` | `price=450000` | CSV cell is `"450000"`, not `"£450,000"` |
| `test_csv_matched_semicolon_separated` | `matched=["garden", "quiet"]` | CSV cell is `"garden;quiet"` |
| `test_csv_commute_empty_when_none` | `commute_minutes=None` | CSV cell is empty string |
| `test_h2c_exporter_calls_connector` | mock connector, 2 listings | `create_comparison` called once |
| `test_h2c_exporter_returns_url` | mock connector returns `{suid_code: "ABC123"}` | result has `comparison_url` ending `/pc/ABC123/overview` |
| `test_h2c_exporter_skipped_no_connector` | `h2c_connector=None` | `ExportResult.warnings` contains "H2C not configured" |
| `test_html_is_self_contained` | full payload | output HTML has no `<link>` to external CSS, no `<script src=...>` |
| `test_html_contains_all_listing_titles` | 3 listings | each title string appears in HTML output |
| `test_pdf_is_valid_format` | full payload | output bytes starts with `%PDF-` |
| `test_export_payload_disclaimer_present` | any format | output contains disclaimer text |
| `test_export_csv_no_pdf_dependency` | CSV format | no import of fpdf2 triggered |

### Integration tests

```bash
# CSV (no dependencies)
uv run pytest tests/skills/export/test_csv_exporter.py -v

# HTML (requires jinja2)
uv pip install "house-hunt[html]"
uv run pytest tests/skills/export/test_html_exporter.py -v

# PDF (requires fpdf2)
uv pip install "house-hunt[pdf]"
uv run pytest tests/skills/export/test_pdf_exporter.py -v

# H2C (requires live credentials)
export H2C_BASE_URL=https://homestocompare.com
export H2C_HARNESS_KEY=<key>
uv run pytest tests/skills/export/test_h2c_exporter.py -m integration -v
```

### CLI smoke tests

```bash
# CSV
uv run house-hunt demo --export csv --export-path /tmp/test.csv
ls -la /tmp/test.csv  # should be >500 bytes

# HTML
uv run house-hunt demo --export html --export-path /tmp/test.html
# Open /tmp/test.html in browser — should show listings without errors

# Export from saved session
uv run house-hunt --list-sessions
uv run house-hunt export --format html --from-session <id> --export-path /tmp/session.html
```

---

## Open Questions

1. **H2C payload schema.** The current `create_comparison` endpoint accepts only
   `{listings, source}`. What is the H2C API contract for the extended payload
   (narrative, affordability, buyer profile)? Does this require a new H2C endpoint
   or an extension of the existing one?

2. **PDF dependencies portability.** `fpdf2` is the lightest option but its formatting
   is limited. If a cleaner PDF is a priority (for sharing with a mortgage broker),
   WeasyPrint produces better output but requires native system libraries. Should the
   decision be deferred to user feedback after Phase 1, or should Weasyprint be
   designed in from the start?

3. **Export as a separate command vs a flag.** The plan has both `house-hunt export
   --format pdf --from-session <id>` (standalone command) and `house-hunt search
   --export pdf` (flag on the search command). Is this duplication justified, or
   should export be a flag only?

4. **Image thumbnails in HTML/PDF.** Including base64-encoded images makes the export
   self-contained but can bloat file size (6 images × ~100KB thumbnail = 600KB).
   Should there be a `--no-images` flag, and should images be thumbnailed before
   embedding (requiring Pillow as a dependency)?

5. **Export rate limiting.** The H2C `create_comparison` endpoint may have rate
   limits. If the buyer exports multiple times (testing different comparison sets),
   should the harness deduplicate (return the existing comparison URL if listings
   haven't changed) or always create new?

6. **Buyer data in exported files.** The CSV and HTML export contain buyer budget
   and priorities. A buyer emailing a CSV to their partner is fine. A buyer
   accidentally sharing it publicly is a privacy risk. Should exports include a
   warning header reminding the buyer this file contains their personal financial
   preferences?

7. **Comparison URL lifespan.** H2C comparison pages at `/pc/[suid_code]` — how long
   do they remain accessible? If they expire, buyers who shared a link months ago will
   get a 404. Should the harness warn buyers that the link may expire, or should H2C
   guarantee permanent URLs for harness-generated comparisons?
