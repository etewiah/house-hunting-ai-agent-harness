from __future__ import annotations

from src.connectors.mock_listing_api import MockListingApi
from src.harness.policies import advice_boundary_notice
from src.harness.session_state import SessionState
from src.harness.tracing import TraceRecorder
from src.models.schemas import BuyerProfile, RankedListing
from src.skills.affordability import estimate_monthly_payment
from src.skills.comparison import compare_homes
from src.skills.explanation import explain_ranked_listing
from src.skills.intake import parse_buyer_brief
from src.skills.offer_brief import generate_offer_brief
from src.skills.ranking import rank_listings
from src.skills.tour_prep import generate_tour_questions


class HouseHuntOrchestrator:
    def __init__(
        self,
        listings: MockListingApi,
        trace_dir: str = ".traces",
        h2c_connector: object | None = None,
    ) -> None:
        self.listings = listings
        self.h2c_connector = h2c_connector
        self.state = SessionState()
        self.tracer = TraceRecorder(trace_dir)

    def intake(self, brief: str) -> BuyerProfile:
        profile = parse_buyer_brief(brief)
        self.state.buyer_profile = profile
        self.tracer.record("intake.profile_created", profile)
        return profile

    def triage(self, limit: int = 5) -> list[RankedListing]:
        if self.state.buyer_profile is None:
            raise ValueError("Cannot triage listings before preference intake.")
        candidates = self.listings.search(self.state.buyer_profile)
        ranked = rank_listings(self.state.buyer_profile, candidates)[:limit]
        self.state.ranked_listings = ranked
        self.tracer.record("triage.ranked_listings", ranked)
        return ranked

    def explain_top_matches(self) -> list[str]:
        explanations = [explain_ranked_listing(item) for item in self.state.ranked_listings]
        self.tracer.record("triage.explanations", explanations)
        return explanations

    def compare_top(self, count: int = 3) -> str:
        listings = [item.listing for item in self.state.ranked_listings[:count]]
        output = compare_homes(listings)
        self.tracer.record("comparison.summary", output)
        return output

    def create_comparison(self, count: int = 2) -> dict[str, object]:
        if self.h2c_connector is None:
            return {"status": "skipped", "reason": "HomesToCompare connector not configured."}
        if len(self.state.ranked_listings) < count:
            return {"status": "skipped", "reason": f"Need at least {count} ranked listings to compare."}
        top = [item.listing for item in self.state.ranked_listings[:count]]
        result = self.h2c_connector.create_comparison(top)
        self.tracer.record("comparison.created", result)
        return result

    def prep_next_steps(self) -> dict[str, object]:
        if not self.state.ranked_listings:
            raise ValueError("Cannot prep next steps before ranking listings.")
        top = self.state.ranked_listings[0].listing
        affordability = estimate_monthly_payment(top)
        questions = generate_tour_questions(top)
        offer = generate_offer_brief(top)
        result = {
            "boundary": advice_boundary_notice(),
            "affordability": affordability,
            "tour_questions": questions,
            "offer_brief": offer,
        }
        self.tracer.record("next_steps.prepared", result)
        return result
