from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SourceLabel = Literal["listing_provided", "user_provided", "estimated", "inferred", "missing"]


@dataclass(frozen=True)
class SourcedValue:
    value: object
    source: SourceLabel


@dataclass(frozen=True)
class BuyerProfile:
    location_query: str
    max_budget: int
    min_bedrooms: int
    max_commute_minutes: int | None = None
    must_haves: list[str] = field(default_factory=list)
    nice_to_haves: list[str] = field(default_factory=list)
    quiet_street_required: bool = False


@dataclass(frozen=True)
class Listing:
    id: str
    title: str
    price: int
    bedrooms: int
    bathrooms: int
    location: str
    commute_minutes: int | None
    features: list[str]
    description: str
    source_url: str


@dataclass(frozen=True)
class RankedListing:
    listing: Listing
    score: float
    matched: list[str]
    missed: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class AffordabilityEstimate:
    listing_id: str
    deposit: int
    loan_amount: int
    monthly_payment: int
    assumptions: list[str]
