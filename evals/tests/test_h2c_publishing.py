from __future__ import annotations

import json

from src.connectors.homestocompare_mapper import (
    build_h2c_public_comparison_payload,
    listing_to_h2c_property_data,
)
from src.connectors.homestocompare_public_connector import HomesToComparePublicConnector
from src.models.schemas import Listing
from src.skills.h2c_publish import publish_h2c_comparison, verify_h2c_photos_page
from src.skills.h2c_publish_validation import validate_h2c_publish_listings
from src.skills.photo_verification import listing_with_photo_verification, verify_listing_photos


class _FakeResponse:
    def __init__(self, body: bytes = b'{"success":true,"comparison_id":"abcdefgh"}') -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


def _listing(
    *,
    listing_id: str = "L1",
    url: str = "https://www.rightmove.co.uk/properties/123456",
    photos: list[str] | None = None,
    verified: bool = True,
) -> Listing:
    photo_urls = photos or ["https://media.example.com/house-1.jpg"]
    external_refs: dict[str, object] = {}
    if verified:
        external_refs["photo_extraction"] = {
            "status": "verified",
            "verified_photo_count": len(photo_urls),
            "photos": [
                {
                    "url": url,
                    "observed_in": "fixture",
                    "content_type": "image/jpeg",
                    "natural_width": 640,
                    "natural_height": 480,
                }
                for url in photo_urls
            ],
        }
    return Listing(
        id=listing_id,
        title=f"Listing {listing_id}",
        price=125000,
        bedrooms=2,
        bathrooms=1,
        location="Preston",
        commute_minutes=None,
        features=["tenant in situ", "investment"],
        description="A verified listing.",
        source_url=url,
        image_urls=photo_urls,
        external_refs=external_refs,
    )


def test_photo_verification_trusts_observed_image_metadata_without_http():
    listing = _listing()

    result = verify_listing_photos(listing, skip_http=True)

    assert result.status == "verified"
    assert len(result.verified) == 1
    assert result.verified[0].url == listing.image_urls[0]
    assert result.rejected == []


def test_photo_verification_rejects_urls_without_observed_metadata_when_http_skipped():
    listing = _listing(verified=False)

    result = verify_listing_photos(listing, skip_http=True)

    assert result.status == "failed"
    assert result.verified == []
    assert result.rejected[0]["reason"] == "no verified image metadata"


def test_h2c_publish_validation_requires_verified_photos():
    listing = _listing(verified=False)

    result = validate_h2c_publish_listings([listing, _listing(listing_id="L2")])

    assert result.ok is False
    assert "verified photo" in result.errors[0]


def test_h2c_mapper_emits_gbp_price_and_image_object_shape():
    listing = _listing(photos=["https://media.example.com/a.jpg", "https://media.example.com/b.jpg"])

    mapped = listing_to_h2c_property_data(listing)

    assert mapped["currency"] == "GBP"
    assert mapped["price_string"] == "£125,000"
    assert mapped["price_float"] == 125000
    assert mapped["image_urls"] == [
        {"url": "https://media.example.com/a.jpg"},
        {"url": "https://media.example.com/b.jpg"},
    ]
    assert mapped["extra_sale_details"]["source_portal"] == "rightmove"


def test_h2c_payload_uses_public_create_comparison_shape():
    left = _listing(listing_id="L1", url="https://www.rightmove.co.uk/properties/123")
    right = _listing(listing_id="L2", url="https://www.onthemarket.com/details/456")

    payload = build_h2c_public_comparison_payload([left, right], comparison={"confidence": "medium"})

    assert payload["left_url"] == left.source_url
    assert payload["right_url"] == right.source_url
    assert payload["left_property_data"]["currency"] == "GBP"
    assert payload["right_property_data"]["image_urls"] == [{"url": right.image_urls[0]}]
    assert payload["source"] == "house-hunting-agent-harness"
    assert payload["house_hunt_comparison"]["confidence"] == "medium"


def test_public_connector_posts_without_service_key(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    connector = HomesToComparePublicConnector("https://homestocompare.com", visitor_session="visitor-123")

    result = connector.create_comparison([_listing(), _listing(listing_id="L2")])

    assert result["status"] == "published"
    assert result["comparison_id"] == "abcdefgh"
    assert result["overview_url"] == "https://homestocompare.com/pc/abcdefgh/overview"
    assert captured["url"] == "https://homestocompare.com/api/create-comparison"
    assert "X-h2c-harness-key" not in captured["headers"]
    assert captured["headers"]["Cookie"] == "h2c_visitor_session=visitor-123"
    assert captured["payload"]["left_property_data"]["price_string"] == "£125,000"


def test_publish_flow_fails_before_h2c_when_photos_are_unverified():
    result = publish_h2c_comparison(
        [_listing(verified=False), _listing(listing_id="L2")],
        skip_photo_http=True,
    )

    assert result.status == "validation_failed"
    assert result.comparison_id is None
    assert any("verified photo" in error for error in result.errors)


def test_publish_flow_reports_render_failure_with_mock_connector():
    class FakeConnector:
        def create_comparison(self, listings, comparison=None):
            return {
                "status": "published",
                "comparison_id": "abcdefgh",
                "overview_url": "https://homestocompare.com/pc/abcdefgh/overview",
                "photos_url": "https://homestocompare.com/pc/abcdefgh/photos",
                "raw_response": {"success": True, "comparison_id": "abcdefgh"},
            }

    result = publish_h2c_comparison(
        [_listing(), _listing(listing_id="L2")],
        connector=FakeConnector(),
        render_verifier=lambda _url, _listings: 0,
        skip_photo_http=True,
    )

    assert result.status == "published_but_failed_verification"
    assert result.photos_submitted == 2
    assert result.photos_rendered == 0


def test_h2c_photos_page_verifier_counts_listings_with_rendered_submitted_urls(monkeypatch):
    left = _listing(listing_id="L1", photos=["https://media.example.com/a.jpg"])
    right = _listing(listing_id="L2", photos=["https://media.example.com/b.jpg"])

    def fake_urlopen(request, timeout):
        return _FakeResponse(
            b'<html><img src="https://media.example.com/a.jpg">'
            b'<img src="https://media.example.com/other.jpg"></html>'
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert verify_h2c_photos_page("https://homestocompare.com/pc/abcdefgh/photos", [left, right]) == 1


def test_listing_with_photo_verification_keeps_only_verified_urls():
    listing = _listing(
        photos=["https://media.example.com/a.jpg", "https://media.example.com/b.jpg"],
        verified=True,
    )
    result = verify_listing_photos(listing, skip_http=True)

    updated = listing_with_photo_verification(listing, result)

    assert updated.image_urls == listing.image_urls
    assert updated.external_refs["photo_extraction"]["status"] == "verified"
