from __future__ import annotations

import csv
from pathlib import Path
from src.models.schemas import Listing


def load_listings_csv(path: str) -> list[Listing]:
    listings: list[Listing] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            listings.append(
                Listing(
                    id=row["id"],
                    title=row["title"],
                    price=int(row["price"]),
                    bedrooms=int(row["bedrooms"]),
                    bathrooms=int(row.get("bathrooms") or 1),
                    location=row["location"],
                    commute_minutes=int(row["commute_minutes"]) if row.get("commute_minutes") else None,
                    features=[item.strip() for item in row.get("features", "").split("|") if item.strip()],
                    description=row.get("description", ""),
                    source_url=row.get("source_url", ""),
                )
            )
    return listings
