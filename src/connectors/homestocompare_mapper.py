from __future__ import annotations

from dataclasses import asdict
from urllib.parse import urlparse

from src.models.schemas import Listing, SourcedValue


def listing_to_h2c_property_data(listing: Listing) -> dict[str, object]:
    """Map a harness Listing into H2C's scraper-listing shape."""

    extra_sale_details = {
        "source": "house-hunting-agent-harness",
        "source_portal": _source_portal(listing.source_url),
        "house_hunt_listing_id": listing.id,
        "commute_minutes": listing.commute_minutes,
        "house_hunt_agent": {
            "external_refs": listing.external_refs,
            "image_url_count": len(listing.image_urls),
        },
    }
    extra_sale_details.update(_decision_details(listing))

    return {
        "title": listing.title,
        "description": listing.description,
        "description_bullet_points": list(listing.features),
        "price_string": _gbp_price_string(listing.price),
        "price_float": listing.price,
        "currency": "GBP",
        "count_bedrooms": listing.bedrooms,
        "count_bathrooms": listing.bathrooms,
        "city": listing.location,
        "country": "United Kingdom",
        "street_address": listing.title,
        "import_url": listing.source_url,
        "reference": listing.id or listing.source_url,
        "image_urls": [{"url": url} for url in listing.image_urls],
        "features": list(listing.features),
        "extra_sale_details": extra_sale_details,
    }


def build_h2c_public_comparison_payload(
    listings: list[Listing],
    *,
    comparison: dict[str, object] | None = None,
    source: str = "house-hunting-agent-harness",
) -> dict[str, object]:
    if len(listings) < 2:
        raise ValueError("At least two listings are required for an H2C comparison.")
    left, right = listings[0], listings[1]
    payload: dict[str, object] = {
        "left_url": left.source_url,
        "right_url": right.source_url,
        "left_property_data": listing_to_h2c_property_data(left),
        "right_property_data": listing_to_h2c_property_data(right),
        "source": source,
        "comparison_entry": "house_hunting_agent",
    }
    if comparison is not None:
        payload["house_hunt_comparison"] = comparison
    return payload


def _gbp_price_string(price: int) -> str:
    return f"£{price:,}" if price > 0 else "Price on request"


def _source_portal(source_url: str) -> str:
    host = urlparse(source_url).netloc.lower()
    if "rightmove" in host:
        return "rightmove"
    if "zoopla" in host:
        return "zoopla"
    if "onthemarket" in host:
        return "onthemarket"
    return host or "unknown"


def _decision_details(listing: Listing) -> dict[str, object]:
    if listing.decision_details is None:
        return {}
    output: dict[str, object] = {}
    raw = asdict(listing.decision_details)
    for key, value in raw.items():
        if value in (None, [], {}):
            continue
        if isinstance(value, dict):
            output[key] = _sourced_value_payload(value)
        else:
            output[key] = value
    return output


def _sourced_value_payload(value: dict[str, object] | SourcedValue) -> object:
    if isinstance(value, SourcedValue):
        return value.value
    if "value" in value:
        return value.get("value")
    return value
