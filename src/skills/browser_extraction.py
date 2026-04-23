"""
Browser-assisted listing extraction using the Pi extension's Node CLI wrappers.

This module bridges Python to the site-specific HTML parsers in
.pi/extensions/house-hunt-browser/bin/ by calling them via subprocess.

It provides:
- property_web_search: find candidate listing URLs via DuckDuckGo HTML
- property_listing_extract: fetch a page and call extract-cli.mjs
- extract_property_listings: batch extraction
- house_hunt_from_web: end-to-end discover → extract → enrich → rank

All extraction diagnostics (parser, quality score, field provenance) are
preserved in the external_refs field of returned listings.
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from dataclasses import dataclass, asdict

DEFAULT_LISTING_SITES = ["rightmove.co.uk", "zoopla.co.uk", "onthemarket.com"]

# Find the extension root relative to this file
EXTENSION_ROOT = Path(__file__).parent.parent.parent / ".pi" / "extensions" / "house-hunt-browser"
EXTRACT_CLI = EXTENSION_ROOT / "bin" / "extract-cli.mjs"
COMMUTE_CLI = EXTENSION_ROOT / "bin" / "commute-cli.mjs"


@dataclass
class ListingExtractionResult:
    """Result of extracting one listing."""
    listing: dict[str, Any]
    diagnostics: dict[str, Any]


class ExtractionError(Exception):
    """Raised when extraction fails."""
    pass


def property_web_search(
    query: str,
    max_results: int = 8,
    sites: list[str] | None = None,
) -> list[dict[str, str]]:
    """
    Search the web for property listing URLs using DuckDuckGo HTML.

    Args:
        query: Search query or buyer brief
        max_results: Max results to return (1-20)
        sites: Domain list (defaults to Rightmove, Zoopla, OnTheMarket)

    Returns:
        List of dicts with 'title' and 'url' keys.
    """
    if sites is None:
        sites = DEFAULT_LISTING_SITES

    # Construct scoped query: "query site:domain1 OR site:domain2 ..."
    site_scope = " OR ".join(f"site:{site}" for site in sites)
    scoped_query = f"{query} {site_scope}"

    try:
        # Fetch DuckDuckGo HTML search results
        url = "https://html.duckduckgo.com/html/"
        params = urllib.parse.urlencode({"q": scoped_query})
        full_url = f"{url}?{params}"

        req = urllib.request.Request(
            full_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; house-hunt-browser/0.1)",
                "Accept-Language": "en-GB,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read(1_000_000).decode("utf-8")  # 1MB cap
    except Exception as e:
        raise ExtractionError(f"Web search failed: {e}")

    # Parse results from HTML
    results = []
    anchor_regex = r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>'
    for match in re.finditer(anchor_regex, html, re.IGNORECASE):
        if len(results) >= max_results * 3:
            break
        try:
            raw_url = urllib.parse.unquote(match.group(1))
            url_obj = urllib.parse.urlparse(raw_url)
            if "uddg=" in url_obj.query:
                # Unwrap DuckDuckGo redirect
                uddg_match = re.search(r"uddg=([^&]+)", url_obj.query)
                if uddg_match:
                    raw_url = urllib.parse.unquote(uddg_match.group(1))

            # Check domain whitelist
            hostname = urllib.parse.urlparse(raw_url).hostname or ""
            if not any(hostname.endswith(site) for site in sites):
                continue

            # Extract title
            title_html = match.group(2)
            title = re.sub(r"<[^>]+>", " ", title_html)
            title = re.sub(r"\s+", " ", title).strip()

            if not title:
                continue

            # Dedup
            if any(r["url"] == raw_url for r in results):
                continue

            results.append({"title": title, "url": raw_url})
        except Exception:
            continue

    return results[:max_results]


def property_listing_extract(
    url: str,
    commute_minutes: int | None = None,
) -> ListingExtractionResult:
    """
    Fetch a listing page and extract normalized listing + diagnostics.

    Args:
        url: Listing URL to extract
        commute_minutes: Optional known commute time (overrides estimation)

    Returns:
        ListingExtractionResult with listing dict and diagnostics.

    Raises:
        ExtractionError if fetch or parse fails.
    """
    try:
        # Fetch the page
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; house-hunt-browser/0.1)",
                "Accept-Language": "en-GB,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read(2_000_000).decode("utf-8", errors="replace")  # 2MB cap
    except Exception as e:
        raise ExtractionError(f"Fetch failed for {url}: {e}")

    try:
        # Call extract-cli.mjs via subprocess
        cmd = ["node", str(EXTRACT_CLI), "--url", url]
        if commute_minutes is not None:
            cmd.extend(["--commute-minutes", str(commute_minutes)])

        result = subprocess.run(
            cmd,
            input=html.encode("utf-8"),
            capture_output=True,
            timeout=10,
            check=False,
        )

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise ExtractionError(f"extract-cli.mjs failed: {stderr}")

        output = json.loads(result.stdout.decode("utf-8"))
        return ListingExtractionResult(
            listing=output["listing"],
            diagnostics=output["diagnostics"],
        )
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Invalid JSON from extract-cli.mjs: {e}")
    except subprocess.TimeoutExpired:
        raise ExtractionError(f"extract-cli.mjs timed out for {url}")
    except FileNotFoundError:
        raise ExtractionError(
            f"extract-cli.mjs not found at {EXTRACT_CLI}. "
            "Ensure Node is installed (npm install in .pi/extensions/house-hunt-browser)"
        )


def extract_property_listings(
    urls: list[str],
    commute_minutes_by_url: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Batch extraction of multiple listing URLs.

    Args:
        urls: List of listing URLs
        commute_minutes_by_url: Optional mapping of URL to known commute time

    Returns:
        Dict with:
          - extracted: list of ListingExtractionResult
          - failed: list of dicts with url and error
    """
    commute_minutes_by_url = commute_minutes_by_url or {}
    extracted = []
    failed = []

    for url in urls:
        try:
            commute = commute_minutes_by_url.get(url)
            result = property_listing_extract(url, commute)
            extracted.append(result)
        except ExtractionError as e:
            failed.append({"url": url, "error": str(e)})

    return {
        "extracted": [
            {"listing": r.listing, "diagnostics": r.diagnostics} for r in extracted
        ],
        "failed": failed,
    }


def enrich_with_commute(
    listings: list[dict[str, Any]],
    destination: str | None = None,
    mode: str = "transit",
) -> list[dict[str, Any]]:
    """
    Enrich listings with heuristic commute estimates.

    Args:
        listings: List of normalized listing dicts
        destination: Commute destination (e.g. "London", "Birmingham")
        mode: Commute mode ('transit', 'driving', 'walking')

    Returns:
        Enriched listings with commute_minutes and commute estimation metadata.
    """
    if not destination:
        return listings

    try:
        cmd = ["node", str(COMMUTE_CLI), "--destination", destination, "--mode", mode]
        result = subprocess.run(
            cmd,
            input=json.dumps(listings).encode("utf-8"),
            capture_output=True,
            timeout=10,
            check=False,
        )

        if result.returncode != 0:
            # Log error but don't fail; return listings unchanged
            return listings

        return json.loads(result.stdout.decode("utf-8"))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        # Silently degrade: return listings unchanged
        return listings


def infer_commute_destination_from_brief(brief: str) -> str | None:
    """
    Infer a commute destination from a buyer brief string.

    Examples:
        "3-bed near Surbiton, commute to Waterloo" → "Surbiton"
        "max 45 min commute to Waterloo" → "Waterloo"
        "2-bed with garden" → None (no destination recognisable)
    """
    try:
        result = subprocess.run(
            ["node", str(COMMUTE_CLI), "--brief", brief, "--infer-only"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            return None
        value = json.loads(result.stdout.decode("utf-8").strip())
        return value if isinstance(value, str) else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def house_hunt_from_web(
    brief: str,
    max_results: int = 6,
    sites: list[str] | None = None,
    min_quality_score: int = 45,
    commute_destination: str | None = None,
    commute_mode: str = "transit",
) -> dict[str, Any]:
    """
    End-to-end house hunt: search → extract → enrich commute → filter by quality.

    Args:
        brief: Buyer brief
        max_results: Max search results (1-20)
        sites: Domain whitelist
        min_quality_score: Minimum quality score to include in results (0-100)
        commute_destination: Optional commute destination for enrichment
        commute_mode: Commute mode for heuristic enrichment

    Returns:
        Dict with:
          - search_results: list of search result dicts
          - extracted: list of extraction results (all)
          - accepted_listings: list of normalized listings passing quality filter
          - failed: list of failed extraction dicts
          - average_quality: average quality score of all extractions
          - filtered_out_low_quality: list of filtered dicts with quality score
    """
    sites = sites or DEFAULT_LISTING_SITES

    # Auto-infer commute destination from brief when not explicitly provided
    commute_destination_inferred = False
    if commute_destination is None:
        commute_destination = infer_commute_destination_from_brief(brief)
        if commute_destination is not None:
            commute_destination_inferred = True

    # Step 1: Search
    try:
        search_results = property_web_search(brief, max_results, sites)
    except ExtractionError as e:
        return {
            "error": str(e),
            "search_results": [],
            "extracted": [],
            "accepted_listings": [],
            "failed": [],
            "average_quality": 0,
            "filtered_out_low_quality": [],
        }

    if not search_results:
        return {
            "search_results": [],
            "extracted": [],
            "accepted_listings": [],
            "failed": [],
            "average_quality": 0,
            "filtered_out_low_quality": [],
        }

    # Step 2: Extract
    extraction_result = extract_property_listings([r["url"] for r in search_results])
    extracted = extraction_result["extracted"]
    failed = extraction_result["failed"]

    if not extracted:
        return {
            "search_results": search_results,
            "extracted": [],
            "accepted_listings": [],
            "failed": failed,
            "average_quality": 0,
            "filtered_out_low_quality": [],
        }

    # Step 3: Compute average quality and filter by threshold
    all_listings = [e["listing"] for e in extracted]
    quality_scores = [e["diagnostics"].get("qualityScore", 0) for e in extracted]
    average_quality = (
        sum(quality_scores) // len(quality_scores) if quality_scores else 0
    )

    accepted_listings = []
    filtered_out = []
    for extraction in extracted:
        score = extraction["diagnostics"].get("qualityScore", 0)
        if score >= min_quality_score:
            accepted_listings.append(extraction["listing"])
        else:
            filtered_out.append({
                "title": extraction["listing"].get("title", "Unknown"),
                "source_url": extraction["listing"].get("source_url", ""),
                "quality_score": score,
                "warnings": extraction["diagnostics"].get("warnings", []),
            })

    # Step 4: Enrich with commute
    enriched = enrich_with_commute(
        accepted_listings,
        commute_destination,
        commute_mode,
    )

    return {
        "search_results": search_results,
        "extracted": extracted,
        "accepted_listings": enriched,
        "failed": failed,
        "average_quality": average_quality,
        "filtered_out_low_quality": filtered_out,
        "commute_destination": commute_destination,
        "commute_destination_inferred": commute_destination_inferred,
        "commute_mode": commute_mode,
        "min_quality_score": min_quality_score,
    }
