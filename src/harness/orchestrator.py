from __future__ import annotations

from src.connectors.mock_listing_api import MockListingApi
from src.harness.policies import advice_boundary_notice
from src.harness.session_state import SessionState
from src.harness.tracing import TraceRecorder
from src.models.schemas import BuyerProfile, ExportOptions, ExportPayload, ExportResult, RankedListing
from src.skills.export import ExportOrchestrator
from src.skills.affordability import estimate_monthly_payment
from src.skills.comparison import compare_homes
from src.skills.explanation import explain_ranked_listing
from src.skills.intake import parse_buyer_brief
from src.skills.listing_search import filter_by_location
from src.skills.offer_brief import generate_offer_brief
from src.skills.ranking import rank_listings
from src.skills.tour_prep import generate_tour_questions


class HouseHuntOrchestrator:
    def __init__(
        self,
        listings: MockListingApi,
        trace_dir: str = ".traces",
        h2c_connector: object | None = None,
        llm: object | None = None,
    ) -> None:
        self.listings = listings
        self.h2c_connector = h2c_connector
        self.llm = llm
        self.state = SessionState()
        self.tracer = TraceRecorder(trace_dir)
        self.exporter = ExportOrchestrator()

    def intake(self, brief: str) -> BuyerProfile:
        profile = parse_buyer_brief(brief, llm=self.llm)
        self.state.buyer_profile = profile
        self.tracer.record("intake.profile_created", profile)
        return profile

    def triage(self, limit: int = 5) -> list[RankedListing]:
        if self.state.buyer_profile is None:
            raise ValueError("Cannot triage listings before preference intake.")
        # Location filter runs on all listings so city resolution works regardless of price.
        # Price/bedroom filter is applied after, scoped to the matched city.
        all_listings = self.listings.all()
        located, warnings = filter_by_location(self.state.buyer_profile.location_query, all_listings)
        self.state.triage_warnings = warnings
        candidates = [
            l for l in located
            if l.price <= self.state.buyer_profile.max_budget * 1.1
            and l.bedrooms >= max(1, self.state.buyer_profile.min_bedrooms - 1)
        ]
        ranked = rank_listings(self.state.buyer_profile, candidates)[:limit]
        self.state.ranked_listings = ranked
        self.tracer.record("triage.ranked_listings", ranked)
        return ranked

    def explain_top_matches(self) -> list[str]:
        explanations = [
            explain_ranked_listing(item, profile=self.state.buyer_profile, llm=self.llm)
            for item in self.state.ranked_listings
        ]
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

    def export(self, options: ExportOptions) -> ExportResult:
        payload = ExportPayload(
            buyer_profile=self.state.buyer_profile,
            ranked_listings=self.state.ranked_listings,
            session_id=self.state.session.session_id if self.state.session is not None else None,
            external_refs=self.state.session.external_refs if self.state.session is not None else {},
        )
        result = self.exporter.export(payload, options)
        self.tracer.record("export.created", result)
        return result
