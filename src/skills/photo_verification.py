from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from src.models.schemas import Listing


@dataclass(frozen=True)
class VerifiedPhoto:
    url: str
    observed_in: str
    status_code: int | None = None
    content_type: str | None = None
    natural_width: int | None = None
    natural_height: int | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PhotoVerificationResult:
    listing_id: str
    status: str
    verified: list[VerifiedPhoto] = field(default_factory=list)
    rejected: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def verify_listing_photos(
    listing: Listing,
    *,
    min_required: int = 1,
    timeout_seconds: int = 8,
    skip_http: bool = False,
) -> PhotoVerificationResult:
    """Verify observed listing photo URLs without inventing replacements."""

    warnings: list[str] = []
    verified: list[VerifiedPhoto] = []
    rejected: list[dict[str, object]] = []

    observed = _observed_photo_metadata(listing)
    for url in _dedupe_urls(listing.image_urls):
        reason = _url_rejection_reason(url)
        if reason is not None:
            rejected.append({"url": url, "reason": reason})
            continue

        metadata = observed.get(url, {})
        observed_in = str(metadata.get("observed_in") or metadata.get("source") or "listing.image_urls")
        natural_width = _optional_int(metadata.get("natural_width"))
        natural_height = _optional_int(metadata.get("natural_height"))
        content_type = _optional_str(metadata.get("content_type"))
        status_code = _optional_int(metadata.get("status_code"))

        if _metadata_proves_image(metadata):
            verified.append(
                VerifiedPhoto(
                    url=url,
                    observed_in=observed_in,
                    status_code=status_code,
                    content_type=content_type,
                    natural_width=natural_width,
                    natural_height=natural_height,
                )
            )
            continue

        if skip_http:
            rejected.append({"url": url, "reason": "no verified image metadata"})
            continue

        http_result = _verify_photo_http(url, timeout_seconds=timeout_seconds)
        if http_result.get("ok") is True:
            verified.append(
                VerifiedPhoto(
                    url=url,
                    observed_in=observed_in,
                    status_code=_optional_int(http_result.get("status_code")),
                    content_type=_optional_str(http_result.get("content_type")),
                    natural_width=natural_width,
                    natural_height=natural_height,
                    warnings=[],
                )
            )
        else:
            rejected.append({"url": url, "reason": str(http_result.get("reason", "verification failed"))})

    if len(verified) < min_required:
        warnings.append(
            f"{listing.id or listing.title} has {len(verified)} verified photo(s); "
            f"{min_required} required."
        )

    status = "verified" if len(verified) >= min_required else "failed"
    return PhotoVerificationResult(
        listing_id=listing.id,
        status=status,
        verified=verified,
        rejected=rejected,
        warnings=warnings,
    )


def listing_with_photo_verification(
    listing: Listing,
    result: PhotoVerificationResult,
) -> Listing:
    external_refs = dict(listing.external_refs)
    external_refs["photo_extraction"] = {
        "status": result.status,
        "source_url": listing.source_url,
        "photo_count": len(listing.image_urls),
        "verified_photo_count": len(result.verified),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "photos": [
            {
                "url": photo.url,
                "observed_in": photo.observed_in,
                "status_code": photo.status_code,
                "content_type": photo.content_type,
                "natural_width": photo.natural_width,
                "natural_height": photo.natural_height,
                "warnings": photo.warnings,
            }
            for photo in result.verified
        ],
        "rejected": result.rejected,
        "warnings": result.warnings,
    }
    return replace(
        listing,
        image_urls=[photo.url for photo in result.verified],
        external_refs=external_refs,
    )


def _verify_photo_http(url: str, *, timeout_seconds: int) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", 200) or 200)
            content_type = str(response.headers.get("content-type", "")).split(";")[0].lower()
            if status_code >= 400:
                return {"ok": False, "status_code": status_code, "reason": f"http {status_code}"}
            if not content_type.startswith("image/"):
                return {
                    "ok": False,
                    "status_code": status_code,
                    "content_type": content_type,
                    "reason": f"non-image content type {content_type or 'unknown'}",
                }
            return {"ok": True, "status_code": status_code, "content_type": content_type}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "reason": f"http {exc.code}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "reason": str(exc.reason)}
    except TimeoutError:
        return {"ok": False, "reason": "timeout"}
    except OSError as exc:
        return {"ok": False, "reason": str(exc)}


def _observed_photo_metadata(listing: Listing) -> dict[str, dict[str, object]]:
    extraction = listing.external_refs.get("photo_extraction")
    if not isinstance(extraction, dict):
        return {}
    raw_photos = extraction.get("photos")
    if not isinstance(raw_photos, list):
        return {}
    photos: dict[str, dict[str, object]] = {}
    for item in raw_photos:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if isinstance(url, str) and url.strip():
            photos[url.strip()] = item
    return photos


def _metadata_proves_image(metadata: dict[str, object]) -> bool:
    content_type = _optional_str(metadata.get("content_type"))
    if content_type and content_type.lower().startswith("image/"):
        return True
    natural_width = _optional_int(metadata.get("natural_width"))
    natural_height = _optional_int(metadata.get("natural_height"))
    return bool(natural_width and natural_width > 0 and natural_height and natural_height > 0)


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        cleaned = str(url).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _url_rejection_reason(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return "not an http(s) URL"
    if not parsed.netloc:
        return "missing host"
    return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
