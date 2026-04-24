from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SourceLabel = Literal["listing_provided", "user_provided", "estimated", "inferred", "missing"]


@dataclass(frozen=True)
class SourcedValue:
    value: object
    source: SourceLabel
    provider: str | None = None
    retrieved_at: str | None = None
    confidence: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CommuteEstimate:
    listing_id: str
    destination: str
    duration_minutes: int | None
    mode: str
    provider: str
    source: SourceLabel
    retrieved_at: str
    confidence: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AreaEvidence:
    category: str
    summary: str
    source_name: str
    source: SourceLabel
    retrieved_at: str
    jurisdiction: str | None = None
    confidence: str | None = None
    details: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AreaData:
    listing_id: str
    evidence: list[AreaEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImageFlag:
    category: str
    label: str
    confidence: str
    note: str
    image_index: int | None = None
    source: SourceLabel = "estimated"


@dataclass(frozen=True)
class ImageAnalysis:
    listing_id: str
    summary: str
    flags: list[ImageFlag] = field(default_factory=list)
    positive_highlights: list[str] = field(default_factory=list)
    condition_warnings: list[str] = field(default_factory=list)
    images_analysed: list[str] = field(default_factory=list)
    images_skipped: int = 0
    model_used: str | None = None
    analysis_date: str | None = None
    source: SourceLabel = "estimated"
    error: str | None = None


@dataclass(frozen=True)
class PropertyDecisionDetails:
    tenure: SourcedValue | None = None
    lease_years_remaining: SourcedValue | None = None
    service_charge_annual: SourcedValue | None = None
    ground_rent_annual: SourcedValue | None = None
    council_tax_band: SourcedValue | None = None
    epc_rating: SourcedValue | None = None
    chain_status: SourcedValue | None = None
    parking_details: SourcedValue | None = None
    outdoor_space: SourcedValue | None = None
    condition_summary: SourcedValue | None = None
    floor_area_sqft: SourcedValue | None = None
    price_per_sqft: SourcedValue | None = None
    flood_risk: SourcedValue | None = None
    broadband: SourcedValue | None = None
    notes: list[str] = field(default_factory=list)


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
    location_data: dict[str, object] = field(default_factory=dict)
    commute_estimates: list[CommuteEstimate] = field(default_factory=list)
    area_data: AreaData | None = None
    image_urls: list[str] = field(default_factory=list)
    image_analysis: ImageAnalysis | None = None
    decision_details: PropertyDecisionDetails | None = None
    external_refs: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RankedListing:
    listing: Listing
    score: float
    matched: list[str]
    missed: list[str]
    warnings: list[str]
    score_breakdown: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ComparisonDimension:
    name: str
    winner_listing_id: str | None
    summaries: dict[str, str] = field(default_factory=dict)
    source: SourceLabel = "inferred"
    confidence: str = "medium"
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VerificationItem:
    listing_id: str | None
    category: str
    question: str
    reason: str
    priority: str = "medium"
    source: SourceLabel = "inferred"


@dataclass(frozen=True)
class ComparisonResult:
    listings: list[Listing]
    recommendation_listing_id: str | None
    recommendation_summary: str
    close_call_score: float
    dimensions: list[ComparisonDimension] = field(default_factory=list)
    trade_offs: list[str] = field(default_factory=list)
    deal_breakers: list[str] = field(default_factory=list)
    verification_items: list[VerificationItem] = field(default_factory=list)
    confidence: str = "medium"
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AffordabilityEstimate:
    listing_id: str
    deposit: int
    loan_amount: int
    monthly_payment: int
    assumptions: list[str]


@dataclass
class ListingNote:
    listing_id: str
    text: str
    created_at: str
    updated_at: str
    source: str


@dataclass
class ShortlistEntry:
    listing: Listing
    added_at: str
    status: str = "active"
    notes: list[ListingNote] = field(default_factory=list)
    ranked_score: float | None = None


@dataclass
class Session:
    session_id: str
    created_at: str
    updated_at: str
    buyer_profile: BuyerProfile | None = None
    shortlist: list[ShortlistEntry] = field(default_factory=list)
    search_history: list[dict[str, object]] = field(default_factory=list)
    generated_outputs: dict[str, object] = field(default_factory=dict)
    external_refs: dict[str, object] = field(default_factory=dict)
    version: int = 1


@dataclass
class ExportOptions:
    format: str
    output_path: str | None = None
    include_images: bool = True
    include_affordability: bool = True
    include_area_data: bool = True
    include_image_analysis: bool = True
    include_notes: bool = True
    max_listings: int = 5


@dataclass(frozen=True)
class ExportPayload:
    buyer_profile: BuyerProfile | None = None
    ranked_listings: list[RankedListing] = field(default_factory=list)
    shortlist: list[ShortlistEntry] = field(default_factory=list)
    generated_outputs: dict[str, object] = field(default_factory=dict)
    session_id: str | None = None
    external_refs: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExportResult:
    format: str
    listing_count: int
    generated_at: str
    output_path: str | None = None
    share_url: str | None = None
    machine_readable_url: str | None = None
    file_size_bytes: int | None = None
    warnings: list[str] = field(default_factory=list)
