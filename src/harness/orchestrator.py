from __future__ import annotations

from src.harness.policies import advice_boundary_notice, check_output_guardrails
from src.harness.session_state import SessionState
from src.harness.tracing import TraceRecorder
from src.models.capabilities import ListingProvider
from src.models.schemas import BuyerProfile, ExportOptions, ExportPayload, ExportResult, Listing, RankedListing
from src.skills.export import ExportOrchestrator
from src.skills.affordability import estimate_monthly_payment
from src.skills.comparison import compare_homes
from src.skills.explanation import explain_ranked_listing
from src.skills.intake import parse_buyer_brief
from src.skills.listing_input import listing_from_dict
from src.skills.listing_search import filter_by_location, filter_listings
from src.skills.offer_brief import generate_offer_brief
from src.skills.ranking import rank_listings
from src.skills.tour_prep import generate_tour_questions


class HouseHuntOrchestrator:
    def __init__(
        self,
        listings: ListingProvider | None,
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
        if self.listings is None:
            raise ValueError(
                "No listing provider configured. In browser-assisted or coding-agent workflows, "
                "gather listings externally and call triage_listings(candidates)."
            )
        candidates = self.listings.search(self.state.buyer_profile)
        return self.triage_listings(candidates, limit=limit)

    def triage_listings(self, candidates: list[Listing], limit: int = 5) -> list[RankedListing]:
        if self.state.buyer_profile is None:
            raise ValueError("Cannot triage listings before preference intake.")
        located, location_warnings = filter_by_location(self.state.buyer_profile.location_query, candidates)
        filtered = filter_listings(self.state.buyer_profile, located)
        self.state.triage_warnings = location_warnings
        ranked = rank_listings(self.state.buyer_profile, filtered)[:limit]
        self.state.ranked_listings = ranked
        self.tracer.record(
            "triage.ranked_listings",
            {"warnings": location_warnings, "count": len(ranked), "items": ranked},
        )
        return ranked

    def triage_listing_dicts(self, candidates: list[dict[str, object]], limit: int = 5) -> list[RankedListing]:
        return self.triage_listings([listing_from_dict(candidate) for candidate in candidates], limit=limit)

    def explain_top_matches(self) -> list[str]:
        explanations = [
            explain_ranked_listing(item, profile=self.state.buyer_profile, llm=self.llm)
            for item in self.state.ranked_listings
        ]
        guardrails = [
            check_output_guardrails(explanation, require_source_label=True)
            for explanation in explanations
        ]
        self.tracer.record("triage.explanations", explanations)
        self.tracer.record(
            "guardrails.checked",
            {"scope": "triage.explanations", "results": guardrails},
        )
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
        self.tracer.record(
            "guardrails.checked",
            {
                "scope": "next_steps",
                "results": [
                    check_output_guardrails(result["boundary"], require_boundary_notice=True),
                    check_output_guardrails(offer, require_boundary_notice=True),
                    check_output_guardrails("\n".join(questions)),
                ],
            },
        )
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
