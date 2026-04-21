from __future__ import annotations

from dataclasses import dataclass, field

PROHIBITED_CLAIMS = [
    "legal advice",
    "mortgage advice",
    "survey advice",
    "inspection advice",
    "fiduciary advice",
]

FAIR_HOUSING_SENSITIVE_RECOMMENDATION_PHRASES = [
    "good schools nearby",
    "safe neighbourhood",
    "safe neighborhood",
    "family-friendly area",
]

SOURCE_LABELS = [
    "listing_provided",
    "user_provided",
    "estimated",
    "inferred",
    "missing",
]


@dataclass(frozen=True)
class GuardrailResult:
    passed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def advice_boundary_notice() -> str:
    return (
        "This is a preparation aid, not legal, mortgage, survey, inspection, "
        "fiduciary, or negotiation advice."
    )


def check_guardrails(text: str) -> list[str]:
    lowered = text.lower()
    return [claim for claim in PROHIBITED_CLAIMS if claim in lowered]


def check_generated_recommendation_language(text: str) -> list[str]:
    lowered = text.lower()
    return [
        phrase
        for phrase in FAIR_HOUSING_SENSITIVE_RECOMMENDATION_PHRASES
        if phrase in lowered
    ]


def check_output_guardrails(
    text: str,
    *,
    require_boundary_notice: bool = False,
    require_source_label: bool = False,
) -> GuardrailResult:
    violations = [
        f"prohibited claim: {claim}"
        for claim in check_guardrails(text)
    ]
    warnings = [
        f"sensitive recommendation language: {phrase}"
        for phrase in check_generated_recommendation_language(text)
    ]

    if require_boundary_notice and not _contains_boundary_notice(text):
        violations.append("missing advice boundary notice")

    if require_source_label and not _contains_source_label(text):
        violations.append("missing source label")

    return GuardrailResult(
        passed=not violations,
        violations=violations,
        warnings=warnings,
    )


def _contains_boundary_notice(text: str) -> bool:
    lowered = text.lower()
    return (
        "not legal" in lowered
        and "mortgage" in lowered
        and ("inspection" in lowered or "survey" in lowered)
    )


def _contains_source_label(text: str) -> bool:
    lowered = text.lower()
    return any(label in lowered for label in SOURCE_LABELS)
