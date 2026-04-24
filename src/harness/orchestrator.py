from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone

from src.harness.policies import advice_boundary_notice, check_output_guardrails
from src.harness.session_state import SessionState
from src.harness.tracing import TraceRecorder
from src.models.capabilities import ListingProvider
from src.models.schemas import BuyerProfile, ExportOptions, ExportPayload, ExportResult, Listing, RankedListing
from src.skills.export import ExportOrchestrator
from src.skills.affordability import estimate_monthly_payment
from src.skills.comparison import build_comparison_result, compare_ranked_homes
from src.skills.explanation import explain_ranked_listing
from src.skills.h2c_publish import publish_h2c_comparison
from src.skills.intake import parse_buyer_brief
from src.skills.listing_input import listing_from_dict
from src.skills.listing_search import filter_by_location, filter_listings
from src.skills.offer_brief import generate_offer_brief
from src.skills.ranking import rank_listings
from src.skills.tour_prep import generate_tour_questions
from src.skills.verification import verification_summary


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

    def _set_pipeline_stage(self, stage: str, message: str, **metrics: object) -> None:
        status = self.state.pipeline_status
        event = {
            "at": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "message": message,
            "metrics": metrics,
        }
        history = status.get("history")
        if isinstance(history, list):
            history.append(event)
        status["current_stage"] = stage
        status["message"] = message
        status["updated_at"] = event["at"]
        status["metrics"] = metrics
        self.tracer.record("pipeline.status", event)

    def get_pipeline_status(self) -> dict[str, object]:
        status = self.state.pipeline_status
        history = status.get("history")
        return {
            "current_stage": status.get("current_stage"),
            "message": status.get("message"),
            "updated_at": status.get("updated_at"),
            "metrics": dict(status.get("metrics") or {}),
            "history": list(history) if isinstance(history, list) else [],
        }

    def get_acquisition_summary(self) -> dict[str, object]:
        return dict(self.state.acquisition_summary)

    def get_area_context_summary(self, max_listings: int = 5) -> dict[str, object]:
        considered = self.state.ranked_listings[:max_listings]
        items: list[dict[str, object]] = []
        for ranked in considered:
            listing = ranked.listing
            if listing.area_data is None or not listing.area_data.evidence:
                continue
            evidence = listing.area_data.evidence
            categories = list(dict.fromkeys([item.category for item in evidence]))
            top_evidence = [
                {
                    "category": item.category,
                    "source": item.source,
                    "summary": item.summary,
                }
                for item in evidence[:2]
            ]
            items.append(
                {
                    "listing_id": listing.id,
                    "title": listing.title,
                    "evidence_count": len(evidence),
                    "categories": categories[:5],
                    "warning_count": len(listing.area_data.warnings),
                    "top_evidence": top_evidence,
                }
            )
        return {
            "listing_count_considered": len(considered),
            "listings_with_area_context": len(items),
            "items": items,
        }

    def get_area_evidence_rollup(self, max_listings: int = 5) -> dict[str, object]:
        considered = self.state.ranked_listings[:max_listings]
        source_counter: Counter[str] = Counter()
        category_counter: Counter[str] = Counter()
        total_evidence = 0
        total_warnings = 0
        listings_with_area = 0

        for ranked in considered:
            listing = ranked.listing
            if listing.area_data is None:
                continue
            if listing.area_data.evidence:
                listings_with_area += 1
            total_warnings += len(listing.area_data.warnings)
            for evidence in listing.area_data.evidence:
                total_evidence += 1
                source_counter[str(evidence.source)] += 1
                category_counter[str(evidence.category)] += 1

        listing_count_considered = len(considered)
        coverage_ratio = (
            listings_with_area / listing_count_considered if listing_count_considered > 0 else 0.0
        )
        estimated_count = int(source_counter.get("estimated", 0))
        estimated_ratio = estimated_count / total_evidence if total_evidence > 0 else 0.0
        if total_evidence == 0 or listings_with_area == 0:
            confidence_band = "low"
            confidence_reason = "No area evidence available for ranked listings."
        elif coverage_ratio >= 0.75 and total_evidence >= 4 and estimated_ratio <= 0.60:
            confidence_band = "high"
            confidence_reason = "Most ranked listings include multi-source area evidence."
        elif coverage_ratio >= 0.40 and total_evidence >= 2:
            confidence_band = "medium"
            confidence_reason = "Some ranked listings include area evidence, but coverage is partial."
        else:
            confidence_band = "low"
            confidence_reason = "Area evidence coverage is sparse or heavily estimated."

        return {
            "listing_count_considered": listing_count_considered,
            "listings_with_area_context": listings_with_area,
            "total_evidence_items": total_evidence,
            "total_area_warnings": total_warnings,
            "evidence_by_source": dict(source_counter),
            "top_categories": dict(category_counter.most_common(5)),
            "coverage_ratio": round(coverage_ratio, 3),
            "estimated_ratio": round(estimated_ratio, 3),
            "confidence_band": confidence_band,
            "confidence_reason": confidence_reason,
        }

    def get_verification_rollup(self, max_listings: int = 5) -> dict[str, object]:
        considered = self.state.ranked_listings[:max_listings]
        summaries = [verification_summary(item.listing) for item in considered]
        total = sum(int(item.get("verification_count", 0) or 0) for item in summaries)
        high = sum(int(item.get("high_priority_count", 0) or 0) for item in summaries)
        return {
            "listing_count_considered": len(considered),
            "total_verification_items": total,
            "high_priority_items": high,
            "items": summaries,
        }

    def intake(self, brief: str) -> BuyerProfile:
        self._set_pipeline_stage("intake.started", "Parsing buyer brief")
        profile = parse_buyer_brief(brief, llm=self.llm)
        self.state.buyer_profile = profile
        self.tracer.record("intake.profile_created", profile)
        self._set_pipeline_stage(
            "intake.completed",
            "Buyer profile captured",
            has_commute_limit=profile.max_commute_minutes is not None,
            must_haves=len(profile.must_haves),
        )
        return profile

    def triage(self, limit: int = 5) -> list[RankedListing]:
        self._set_pipeline_stage("triage.started", "Searching and ranking listings", limit=limit)
        if self.state.buyer_profile is None:
            self._set_pipeline_stage("triage.failed", "Cannot rank before intake")
            raise ValueError("Cannot triage listings before preference intake.")
        if self.listings is None:
            self._set_pipeline_stage("triage.failed", "No listing provider configured")
            raise ValueError(
                "No listing provider configured. In browser-assisted or coding-agent workflows, "
                "gather listings externally and call triage_listings(candidates)."
            )
        candidates = self.listings.search(self.state.buyer_profile)
        return self.triage_listings(candidates, limit=limit)

    def triage_listings(self, candidates: list[Listing], limit: int = 5) -> list[RankedListing]:
        self._set_pipeline_stage(
            "triage.candidates_received",
            "Ranking supplied candidate listings",
            candidate_count=len(candidates),
            limit=limit,
        )
        if self.state.buyer_profile is None:
            self._set_pipeline_stage("triage.failed", "Cannot rank before intake")
            raise ValueError("Cannot triage listings before preference intake.")
        located, location_warnings = filter_by_location(self.state.buyer_profile.location_query, candidates)
        filtered = filter_listings(self.state.buyer_profile, located)
        self.state.triage_warnings = location_warnings
        ranked_all = rank_listings(self.state.buyer_profile, filtered)
        ranked = ranked_all[:limit]
        exclusion_reasons = {
            "location_filter": max(0, len(candidates) - len(located)),
            "requirement_filters": max(0, len(located) - len(filtered)),
            "rank_limit": max(0, len(ranked_all) - len(ranked)),
        }
        extraction_coverage = {
            "with_quality_score": sum(
                1
                for listing in candidates
                if isinstance(listing.external_refs, dict)
                and listing.external_refs.get("extraction_quality_score") is not None
            ),
            "with_extraction_warnings": sum(
                1
                for listing in candidates
                if isinstance(listing.external_refs, dict)
                and isinstance(listing.external_refs.get("extraction_warnings"), list)
                and len(listing.external_refs.get("extraction_warnings") or []) > 0
            ),
        }
        summary = {
            "candidate_count": len(candidates),
            "located_count": len(located),
            "filtered_count": len(filtered),
            "ranked_count": len(ranked),
            "warning_count": len(location_warnings),
            "limit": limit,
            "exclusion_reasons": exclusion_reasons,
            "extraction_coverage": extraction_coverage,
        }
        self.state.acquisition_summary = summary
        self.state.ranked_listings = ranked
        self.tracer.record(
            "triage.ranked_listings",
            {"warnings": location_warnings, "count": len(ranked), "items": ranked},
        )
        self.tracer.record("triage.acquisition_summary", summary)
        self._set_pipeline_stage(
            "triage.completed",
            "Ranked listings ready",
            located_count=len(located),
            filtered_count=len(filtered),
            ranked_count=len(ranked),
            warning_count=len(location_warnings),
        )
        return ranked

    def triage_listing_dicts(self, candidates: list[dict[str, object]], limit: int = 5) -> list[RankedListing]:
        self._set_pipeline_stage(
            "triage.normalizing_input",
            "Normalizing listing dictionaries",
            candidate_count=len(candidates),
        )
        return self.triage_listings([listing_from_dict(candidate) for candidate in candidates], limit=limit)

    def explain_top_matches(self) -> list[str]:
        self._set_pipeline_stage(
            "explanations.started",
            "Generating explanation summaries",
            listing_count=len(self.state.ranked_listings),
        )
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
        self._set_pipeline_stage(
            "explanations.completed",
            "Explanations generated",
            explanation_count=len(explanations),
            guardrails_checked=len(guardrails),
        )
        return explanations

    def compare_top(self, count: int = 3) -> str:
        self._set_pipeline_stage("comparison.started", "Building side-by-side comparison", count=count)
        output = compare_ranked_homes(self.state.ranked_listings, count=count)
        self.tracer.record("comparison.summary", output)
        self._set_pipeline_stage(
            "comparison.completed",
            "Comparison ready",
            compared_count=len(self.state.ranked_listings[:count]),
        )
        return output

    def compare_top_structured(self, count: int = 3) -> dict[str, object]:
        self._set_pipeline_stage("comparison.structured_started", "Building structured comparison", count=count)
        result = build_comparison_result(self.state.ranked_listings, max_listings=count)
        self.tracer.record("comparison.structured", result)
        self._set_pipeline_stage(
            "comparison.structured_completed",
            "Structured comparison ready",
            compared_count=len(result.listings),
            confidence=result.confidence,
        )
        return {
            "recommendation_listing_id": result.recommendation_listing_id,
            "recommendation_summary": result.recommendation_summary,
            "close_call_score": result.close_call_score,
            "confidence": result.confidence,
            "warnings": result.warnings,
            "trade_offs": result.trade_offs,
            "deal_breakers": result.deal_breakers,
            "dimensions": [
                {
                    "name": item.name,
                    "winner_listing_id": item.winner_listing_id,
                    "summaries": item.summaries,
                    "source": item.source,
                    "confidence": item.confidence,
                    "warnings": item.warnings,
                }
                for item in result.dimensions
            ],
            "verification_items": [
                {
                    "listing_id": item.listing_id,
                    "category": item.category,
                    "question": item.question,
                    "reason": item.reason,
                    "priority": item.priority,
                    "source": item.source,
                }
                for item in result.verification_items
            ],
        }

    def create_comparison(self, count: int = 2) -> dict[str, object]:
        if self.h2c_connector is None:
            return {"status": "skipped", "reason": "HomesToCompare connector not configured."}
        if len(self.state.ranked_listings) < count:
            return {"status": "skipped", "reason": f"Need at least {count} ranked listings to compare."}
        top = [item.listing for item in self.state.ranked_listings[:count]]
        comparison = self.compare_top_structured(count=count)
        result = publish_h2c_comparison(
            top,
            comparison=comparison,
            connector=self.h2c_connector,
            verify_rendered_photos=True,
        ).as_dict()
        self.tracer.record("comparison.created", result)
        return result

    def prep_next_steps(self) -> dict[str, object]:
        self._set_pipeline_stage("next_steps.started", "Preparing affordability and tour guidance")
        if not self.state.ranked_listings:
            self._set_pipeline_stage("next_steps.failed", "No ranked listings available")
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
        self._set_pipeline_stage(
            "next_steps.completed",
            "Next-step guidance ready",
            tour_question_count=len(questions),
        )
        return result

    def export(self, options: ExportOptions) -> ExportResult:
        self._set_pipeline_stage("export.started", "Exporting report", format=options.format)
        payload = ExportPayload(
            buyer_profile=self.state.buyer_profile,
            ranked_listings=self.state.ranked_listings,
            generated_outputs={
                "acquisition_summary": self.state.acquisition_summary,
                "area_context_summary": self.get_area_context_summary(max_listings=options.max_listings),
                "area_evidence_rollup": self.get_area_evidence_rollup(max_listings=options.max_listings),
                "verification_rollup": self.get_verification_rollup(max_listings=options.max_listings),
                "structured_comparison": asdict(
                    build_comparison_result(
                        self.state.ranked_listings,
                        max_listings=options.max_listings,
                    )
                ),
                "pipeline_status": self.get_pipeline_status(),
            },
            session_id=self.state.session.session_id if self.state.session is not None else None,
            external_refs=self.state.session.external_refs if self.state.session is not None else {},
        )
        result = self.exporter.export(payload, options)
        self.tracer.record("export.created", result)
        self._set_pipeline_stage(
            "export.completed",
            "Export completed",
            format=options.format,
            listing_count=result.listing_count,
        )
        return result
