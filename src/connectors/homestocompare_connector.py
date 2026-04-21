from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict

from src.models.schemas import BuyerProfile, Listing
from src.skills.listing_search import filter_listings


class HomesToCompareConnector:
    """Direct HTTP connector for HomesToCompare APIs.

    This is intentionally not an MCP client. `mcp_client.py` remains reserved for
    protocol-level MCP integration.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def create_comparison(self, listings: list[Listing]) -> dict[str, object]:
        payload = {
            "listings": [asdict(listing) for listing in listings],
            "source": "house-hunting-agent-harness",
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/house-hunt/create-comparison",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-h2c-harness-key": self.api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))


class H2CListingConnector:
    """Read-only listing search connector for HomesToCompare."""

    def __init__(self, base_url: str, read_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.read_key = read_key

    def search(self, profile: BuyerProfile, limit: int = 200) -> list[Listing]:
        params = urllib.parse.urlencode(
            {
                "location": profile.location_query,
                "max_budget": profile.max_budget,
                "min_bedrooms": max(1, profile.min_bedrooms - 1),
                "limit": limit,
            }
        )
        req = urllib.request.Request(
            f"{self.base_url}/api/listings/search?{params}",
            headers={"x-h2c-read-key": self.read_key},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
        listings = [_row_to_listing(row) for row in rows]
        return filter_listings(profile, listings)


def _row_to_listing(row: dict[str, object]) -> Listing:
    price = row.get("price")
    if price is None:
        price = row.get("price_sale_current", 0)
        if isinstance(price, int):
            price = round(price / 100)

    return Listing(
        id=str(row.get("id", "")),
        title=str(row.get("title") or row.get("ai_suggested_title") or "Untitled"),
        price=int(price or 0),
        bedrooms=int(row.get("bedrooms") or row.get("count_bedrooms") or 0),
        bathrooms=int(row.get("bathrooms") or row.get("count_bathrooms") or 0),
        location=str(row.get("location") or row.get("market") or ""),
        commute_minutes=None,
        features=list(row.get("features") or row.get("sale_listing_features") or []),
        description=str(row.get("description") or row.get("description_short") or ""),
        source_url=str(row.get("source_url") or row.get("listing_url") or row.get("import_url") or ""),
    )
