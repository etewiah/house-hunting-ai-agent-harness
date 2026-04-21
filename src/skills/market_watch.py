from __future__ import annotations

from src.models.schemas import BuyerProfile


def build_market_watch(profile: BuyerProfile) -> dict[str, object]:
    return {
        "location_query": profile.location_query,
        "max_budget": profile.max_budget,
        "min_bedrooms": profile.min_bedrooms,
        "frequency": "daily",
        "approval_required_before_contacting_agents": True,
    }
