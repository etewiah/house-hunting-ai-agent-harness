from __future__ import annotations

from dataclasses import dataclass, field
from src.models.schemas import BuyerProfile, RankedListing, Session


@dataclass
class SessionState:
    buyer_profile: BuyerProfile | None = None
    ranked_listings: list[RankedListing] = field(default_factory=list)
    triage_warnings: list[str] = field(default_factory=list)
    approvals: list[str] = field(default_factory=list)
    session: Session | None = None
    pipeline_status: dict[str, object] = field(
        default_factory=lambda: {
            "current_stage": "idle",
            "message": "Ready",
            "updated_at": None,
            "metrics": {},
            "history": [],
        }
    )
