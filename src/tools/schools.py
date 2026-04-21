from __future__ import annotations


def summarize_school_context(location: str) -> dict[str, object]:
    return {
        "location": location,
        "source": "not_configured",
        "summary": "School context connector not configured; use official sources before making decisions.",
    }
