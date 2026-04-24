import json

from src.connectors.homestocompare_connector import HomesToCompareConnector
from src.models.schemas import Listing


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b'{"status":"ok"}'


def test_h2c_create_comparison_sends_structured_comparison(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    connector = HomesToCompareConnector("https://homestocompare.com", "secret")
    listing = Listing(
        id="L1",
        title="Example home",
        price=300000,
        bedrooms=2,
        bathrooms=1,
        location="Birmingham",
        commute_minutes=20,
        features=["parking"],
        description="",
        source_url="https://example.com/listing",
    )

    result = connector.create_comparison(
        [listing],
        comparison={
            "recommendation_listing_id": "L1",
            "trade_offs": ["Example trade-off"],
            "verification_items": [{"question": "Confirm commute."}],
        },
    )

    assert result["status"] == "ok"
    assert captured["url"] == "https://homestocompare.com/api/house-hunt/create-comparison"
    assert captured["payload"]["source"] == "house-hunting-agent-harness"
    assert captured["payload"]["comparison"]["recommendation_listing_id"] == "L1"
    assert captured["payload"]["comparison"]["verification_items"][0]["question"] == "Confirm commute."
