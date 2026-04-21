PROHIBITED_CLAIMS = [
    "legal advice",
    "mortgage advice",
    "survey advice",
    "inspection advice",
    "fiduciary advice",
]


def advice_boundary_notice() -> str:
    return (
        "This is a preparation aid, not legal, mortgage, survey, inspection, "
        "fiduciary, or negotiation advice."
    )


def check_guardrails(text: str) -> list[str]:
    lowered = text.lower()
    return [claim for claim in PROHIBITED_CLAIMS if claim in lowered]

