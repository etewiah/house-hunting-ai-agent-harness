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
