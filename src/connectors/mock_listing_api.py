from __future__ import annotations

import json
from pathlib import Path
from src.models.schemas import BuyerProfile, Listing
from src.skills.listing_search import filter_listings


class MockListingApi:
    def __init__(self, data_path: str) -> None:
        self.data_path = Path(data_path)

    def all(self) -> list[Listing]:
        listings: list[Listing] = []
        for line in self.data_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            listings.append(Listing(**raw))
        return listings

    def search(self, profile: BuyerProfile) -> list[Listing]:
        return filter_listings(profile, self.all())

    def get_listing(self, listing_id: str) -> Listing | None:
        return next((listing for listing in self.all() if listing.id == listing_id), None)
