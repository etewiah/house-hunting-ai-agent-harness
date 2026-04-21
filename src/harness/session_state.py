from __future__ import annotations

from dataclasses import dataclass, field
from src.models.schemas import BuyerProfile, RankedListing


@dataclass
class SessionState:
    buyer_profile: BuyerProfile | None = None
    ranked_listings: list[RankedListing] = field(default_factory=list)
    approvals: list[str] = field(default_factory=list)
